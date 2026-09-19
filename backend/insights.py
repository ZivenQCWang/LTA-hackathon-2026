"""Schedule-derived decision support. No ridership or service-time estimates."""
from collections import defaultdict
from math import ceil
from .planner import capacity_at


def score_breakdown(plan):
    weighted=sum((a['overrun_days'] or 0)*{1:100,2:10,3:1}[a['contract_priority']]*
                 {1:1.3,2:1.2,3:1}[a['activity_priority']] for a in plan['activities'])
    m=plan['metrics']; scenario=plan['scenario']
    return dict(delay=round(weighted if scenario!='B' else 0,2),
                extra_access=7*m['excess_nights'] if scenario!='A' else 0,
                eclo=5*m['eclo_nights'] if scenario!='A' else 0,
                total=m['objective'],eligible=plan['audit']['passed'] and m['remaining_workload']==0,
                weighted_delay=round(weighted,2))


def explain_issue(instance, activity, scenario):
    a=activity
    reasons=list(a['reasons']); blockers=list(a.get('blockers',[]))
    if scenario=='A':
        nights=a['total_accesses']
        policy='Scenario A forbids ECLO.'
    elif scenario=='C':
        # C has at most two ECLO accesses per activity: at most one extra
        # standard work unit in total, not 1.5x yield for every week.
        nights=max(ceil(a['total_accesses']/1.5),a['total_accesses']-1)
        policy='Scenario C allows at most two ECLO accesses per activity, within one two-week window per affected line.'
    else:
        nights=ceil(a['total_accesses']/1.5)
        policy='This lower bound already assumes maximum ECLO yield.'
    earliest=a['start_week']+nights-1
    deadline=instance['projects'][a['contract_number']]['deadline_week']
    if earliest>deadline:
        detail=(f'{a["total_accesses"]} work units starting in week {a["start_week"]}, with at most one access per week, '
                f'cannot finish before week {earliest}; the target is week {deadline}. '
                +policy)
        reasons.insert(0,'Workload cannot fit between its planned start and target')
        blockers.insert(0,dict(rule='workload_window',week=a['start_week'],night=None,detail=detail,other_activity=None,locations=[]))
    return dict(activity_id=a['activity_id'],contract_number=a['contract_number'],overrun_days=a['overrun_days'],remaining=a['remaining_workload'],
                predecessor=a.get('predecessor_activity_id'),reasons=reasons,blockers=blockers)


def analyse(instance, roster, plan):
    activities={a['activity_id']:a for a in plan['activities']}
    occupancy=defaultdict(list); exposure=defaultdict(lambda:dict(activities=set(),stations=set(),locations=set()))
    loads=defaultdict(list)
    for row in plan['accesses']:
        a=activities[row['activity_id']]
        for loc in a['locations']: occupancy[row['week'],row['night'],loc].append(a['activity_id'])
        for pid in row['crew_ids']: loads[pid,row['week']].append(row)
        if row['eclo']:
            for line in a['affected_lines']:
                item=exposure[line,row['week'],row['night']]
                item['activities'].add(a['activity_id'])
                item['locations'].update(loc for loc in a['footprint'] if loc.split(':')[1]==line)
                item['stations'].update(loc.split(':')[2] for loc in a['footprint'] if loc.startswith('PLAT:'+line+':'))
    service=[dict(line=line,week=w,night=n,activities=sorted(v['activities']),stations=sorted(v['stations']),locations=sorted(v['locations']))
             for (line,w,n),v in sorted(exposure.items(),key=lambda x:(x[0][1],x[0][2],x[0][0]))]
    sharing=[dict(week=w,night=n,location=loc,activities=sorted(ids)) for (w,n,loc),ids in sorted(occupancy.items()) if len(ids)>1]
    by_location=defaultdict(set)
    for w,n,loc in occupancy: by_location[w,loc].add(n)
    capacity=[dict(week=w,location=loc,used=len(nights),nominal=capacity_at(instance,plan.get('options',{}),w,loc),
                   excess=max(0,len(nights)-capacity_at(instance,plan.get('options',{}),w,loc))) for (w,loc),nights in by_location.items()]
    capacity.sort(key=lambda x:(-x['excess'],-x['used'],x['week'],x['location']))
    crew=[dict(id=p['id'],name=p['name'],role=p['role'],limit=p['max_shifts'],
               total=sum(len(v) for (pid,_),v in loads.items() if pid==p['id']),
               peak=max((len(v) for (pid,_),v in loads.items() if pid==p['id']),default=0),
               weeks=[dict(week=w,shifts=len(rows)) for (pid,w),rows in sorted(loads.items()) if pid==p['id']]) for p in roster]
    contracts=[]
    for contract in plan['contracts']:
        jobs=[a for a in plan['activities'] if a['contract_number']==contract['contract_number']]
        required=sum(a['total_accesses'] for a in jobs); remaining=sum(a['remaining_workload'] for a in jobs)
        contracts.append(dict(contract,activities=len(jobs),workload=required,remaining=remaining,
                              scheduled_percent=round(100*(required-remaining)/required,1) if required else 0,
                              shifts=sum(len(a['accesses']) for a in jobs),
                              dependencies=sorted({a['predecessor_activity_id'] for a in jobs if a.get('predecessor_activity_id')})))
    return dict(score=score_breakdown(plan),sharing=sharing,co_shared_shifts=len({(aid,g['week'],g['night']) for g in sharing for aid in g['activities']}),
                shared_location_slots_saved=sum(len(g['activities'])-1 for g in sharing),capacity=capacity,crew=crew,contracts=contracts,
                passenger=dict(eclo_line_nights=len(service),engineering_footprint_stations=len({(e['line'],s) for e in service for s in e['stations']}),
                               events=service,has_demand_data=False,
                               explanation='ECLO exposure from scheduled engineering footprints on the synthetic Alpha/Beta network. These are planning indicators, not passenger counts, confirmed station closures or journey delays.'),
                issues=[explain_issue(instance,a,plan['scenario'])
                        for a in plan['activities'] if a['remaining_workload'] or (a['overrun_days'] or 0)>0],
                search=plan.get('search',{'evaluated':3,'method':plan['method'],'candidates':[]}))


def comparison(instance, roster, plans, selected):
    current=plans[selected]; details=analyse(instance,roster,current)
    summaries=[]
    for scenario,plan in plans.items():
        info=details if scenario==selected else analyse(instance,roster,plan)
        summaries.append(dict(scenario=scenario,metrics=plan['metrics'],score=info['score'],
                              co_shared_shifts=info['co_shared_shifts'],eclo_line_nights=info['passenger']['eclo_line_nights'],
                              applied_change=bool(plan.get('options')),options=plan.get('options',{})))
    for issue in details['issues']:
        issue['alternatives']=[]
        job=next(a for a in current['activities'] if a['activity_id']==issue['activity_id'])
        for scenario,plan in plans.items():
            if scenario==selected or not plan['audit']['passed'] or plan.get('options',{})!=current.get('options',{}): continue
            alternative=next(a for a in plan['activities'] if a['activity_id']==job['activity_id'])
            if alternative['completion_date'] and (not job['completion_date'] or alternative['completion_date']<job['completion_date']):
                issue['alternatives'].append(dict(scenario=scenario,completion_date=alternative['completion_date'],
                                                  eclo_nights=plan['metrics']['eclo_nights'],excess_nights=plan['metrics']['excess_nights']))
    return dict(scenarios=summaries,details=details,same_conditions=len({str(sorted(p.get('options',{}).items())) for p in plans.values()})==1)


def brief(instance, plan, audience, week, night, contract=None):
    jobs={a['activity_id']:a for a in plan['activities']}
    rows=[r for r in plan['accesses'] if r['week']==week and r['night']==night and (not contract or r['contract_number']==contract)]
    title=f'PLiZ · {audience.capitalize()} draft · Scenario {plan["scenario"]} · Week {week}, night {night}'
    lines=[title,'Synthetic hackathon planning data. Draft for review; not an operational permit or public service notice.','']
    if audience=='passenger':
        extended=[r for r in rows if r['eclo']]
        if not extended:
            lines.append('No early-closure/late-opening work is scheduled in this selected slot. Standard engineering work alone does not imply a passenger service closure.')
        else:
            affected=sorted({line for r in extended for line in jobs[r['activity_id']]['affected_lines']})
            stations=sorted({loc.split(':')[1]+' '+loc.split(':')[2] for r in extended for loc in jobs[r['activity_id']]['footprint'] if loc.startswith('PLAT:')})
            lines.extend(['Engineering work requiring extended hours is proposed on: '+', '.join(affected)+'.',
                          'Stations within the engineering/safety footprint: '+', '.join(stations)+'.',
                          'Exact service times, affected passenger journeys, alternative routes and shuttle arrangements are unconfirmed. Obtain operator-approved details before publishing.'])
    else:
        lines.append(f'{len(rows)} planned activity shift(s). Completion is not recorded by this planning prototype.')
        for row in rows:
            a=jobs[row['activity_id']]
            lines.extend(['',f'{a["activity_id"]} · {a["contract_number"]} · {a["line"]} {a["bound"]}',
                          f'Locations: {", ".join(a["locations"])}',
                          f'Possession: {a["access_type"]}; work nature: {a["nature"]}; '+('ECLO, 1.5 work units.' if row['eclo'] else 'standard access, 1 work unit.'),
                          'Crew: '+', '.join(row['crew_names']),
                          f'Predecessor: {a.get("predecessor_activity_id") or "none"}; target: {a["deadline"]}; scheduled finish: {a["completion_date"] or "incomplete"}.'])
        lines.extend(['','OCC approval, possession master assignment, isolation/handover times and field completion must be confirmed outside PLiZ.'])
    return dict(title=title,text='\n'.join(lines),draft=True)
