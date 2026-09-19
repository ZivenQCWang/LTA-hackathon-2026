"""Deterministic dispatch heuristic and a separate audit of its output."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from itertools import combinations
from math import ceil
from .domain import conflict, week_end

PLANNER_VERSION = '2026-09-19-scenario-c-tradeoffs-v3'


def leave_weeks(value):
    weeks = set()
    for part in value.replace(' ', '').split(','):
        if not part:
            continue
        bounds = part.split('-')
        if len(bounds) > 2 or not all(x.isdigit() for x in bounds):
            raise ValueError('Leave weeks must look like 5,8,12-14.')
        lo, hi = int(bounds[0]), int(bounds[-1])
        if not 1 <= lo <= hi <= 104:
            raise ValueError('Leave weeks must be within 1–104.')
        weeks.update(range(lo, hi + 1))
    return weeks


def skill(a):
    return 'electrical' if a['nature'] == 'Live' else 'consist' if 'Consist' in a['nature'] else 'construction' if a['activity_type'] == 'Construction' else 'track'


def affected_week(options, week):
    return options.get('week', 1) <= week < options.get('week', 1) + options.get('duration', 1)


def capacity_at(instance, options, week, location):
    if affected_week(options, week) and options.get('capacity_location') == location:
        return options['capacity_nights']
    return instance['supply'][location]


def access_changes(before, after):
    def signatures(rows):
        return {(r['activity_id'], r['access_seq']): (r['week'], r['night'], tuple(sorted(r['crew_ids'])), r['eclo']) for r in rows}
    old, new = signatures(before), signatures(after)
    return sum(old.get(key) != new.get(key) for key in old.keys() | new.keys())


def available(p, week, options):
    return p['active'] and week not in leave_weeks(p['unavailable']) and not (affected_week(options, week) and p['id'] in options.get('absent_ids', []))


def generate(instance, roster, scenario='A', options=None, reference=None):
    options = options or {}
    candidates = [_generate(instance, roster, scenario, options, reference, order) for order in range(3)]
    names=['Priority first','Least slack first','Deadline first']
    rank=lambda p:(p['metrics']['remaining_workload'], len(p['audit']['violations']), p['metrics']['objective'], p['metrics']['changed_accesses'], p['metrics']['last_week'])
    if scenario=='C':
        # In C, a small low-priority slip can cost less than two ECLO nights.
        # Replan complete schedules to measure downstream effects as well. Keep
        # the original candidates, so this bounded search cannot worsen them.
        seed=min(candidates,key=rank)
        optional=sorted({r['activity_id'] for r in seed['accesses'] if r['eclo'] and r['week']>=options.get('week',1)})[:8]
        for aid in optional:
            for order,name in enumerate(names[:3]):
                candidates.append(_generate(instance,roster,scenario,options,reference,order,standard_only={aid}))
                names.append(f'{name} · standard nights for {aid}')
    chosen=min(candidates,key=rank)
    method='Three greedy orderings'+('; compare optional ECLO against standard-night alternatives in Scenario C' if scenario=='C' else '')+'. Choose complete work, fewer audit violations, then lower scenario penalty and fewer assignment changes.'
    chosen['method']='Bounded deterministic scheduling search; optimality is not guaranteed.'
    chosen['search']=dict(evaluated=len(candidates),method=method,
                          candidates=[dict(order=name,selected=p is chosen,objective=p['metrics']['objective'],remaining=p['metrics']['remaining_workload'],violations=len(p['audit']['violations']),changed=p['metrics']['changed_accesses']) for name,p in zip(names,candidates)])
    return chosen


def _generate(instance, roster, scenario, options, reference, order, standard_only=frozenset()):
    acts = {a['activity_id']: a for a in instance['activities']}
    remaining = {aid: a['total_accesses'] * 2 for aid, a in acts.items()}
    slots, supply, budgets = defaultdict(list), defaultdict(set), defaultdict(set)
    crew_week, crew_total = Counter(), Counter()
    crew_slot, eclo_weeks = defaultdict(set), defaultdict(set)
    rows, finished = [], {}
    assigned, reasons, blockers = defaultdict(list), defaultdict(Counter), defaultdict(dict)
    def blocked(aid, rule, week, night, detail, other=None, locations=None):
        key=(rule, other)
        if key not in blockers[aid] and len(blockers[aid]) < 6:
            blockers[aid][key]=dict(rule=rule,week=week,night=night,detail=detail,
                                   other_activity=other,locations=(locations or [])[:6])
    old = {(r['activity_id'], r['access_seq']): r for r in (reference or {}).get('accesses', [])}
    collisions = {(a, b): conflict(acts[a], acts[b]) for a, b in combinations(acts, 2)}
    def collides(a, b):
        return collisions.get((a, b), collisions.get((b, a), False))
    def commit(a, week, night, team, eclo):
        aid, cid = a['activity_id'], a['contract_number']
        row = dict(activity_id=aid, contract_number=cid, activity_type=a['activity_type'], week=week, night=night,
                   access_seq=len(assigned[aid])+1, eclo=eclo, crew_ids=[p['id'] for p in team], crew_names=[p['name'] for p in team],
                   date=str(date.fromisoformat(instance['start'])+timedelta(days=(week-1)*7+night-1)), skill=skill(a))
        rows.append(row); slots[week, night].append(row); assigned[aid].append(row)
        for loc in a['locations']: supply[week, loc].add(night)
        budgets[cid, a['activity_type'], week].add(night)
        for p in team:
            crew_week[week, p['id']] += 1; crew_total[p['id']] += 1; crew_slot[week, night].add(p['id'])
        if eclo:
            for line in a['affected_lines']: eclo_weeks[line].add(week)
        remaining[aid] = max(0, remaining[aid] - (3 if eclo else 2))
        if not remaining[aid]: finished[aid] = week
    if reference:
        by_person = {p['id']: p for p in roster}
        for r in reference['accesses']:
            if r['week'] < options.get('week', 1):
                commit(acts[r['activity_id']], r['week'], r['night'], [by_person[x] for x in r['crew_ids']], r['eclo'])
    limit = min(104, max(instance['horizon'], max(a['start_week'] for a in acts.values()))+52)
    for week in range(options.get('week', 1) if reference else 1, limit+1):
        for aid,a in acts.items():
            pred=a['predecessor_activity_id']
            if remaining[aid] and a['start_week']<=week and pred and finished.get(pred,1000)>=week:
                reasons[aid]['Waiting for predecessor completion']+=1
                blocked(aid,'precedence',week,None,f'{pred} must finish in a strictly earlier week before {aid} can start.',pred)
        ready = [a for aid, a in acts.items() if remaining[aid] and a['start_week'] <= week and
                 (not a['predecessor_activity_id'] or finished.get(a['predecessor_activity_id'], 1000) < week)]
        def key(a):
            deadline = instance['projects'][a['contract_number']]['deadline_week']
            slack = deadline-week-ceil(remaining[a['activity_id']]/2)
            return ((a['contract_priority'], slack, a['activity_priority']) if order == 0 else
                    (slack, a['contract_priority'], a['activity_priority']) if order == 1 else
                    (deadline, a['contract_priority'], -len(a['footprint']))) + (a['activity_id'],)
        for a in sorted(ready, key=key):
            aid, cid = a['activity_id'], a['contract_number']; p = instance['projects'][cid]
            target = old.get((aid, len(assigned[aid])+1))
            if reference and target and target['week'] > week: continue
            if scenario == 'B' and week > p['deadline_week']:
                reasons[aid]['Fixed deadline reached'] += 1
                blocked(aid,'deadline',week,None,'Scenario B cannot schedule work after the planned completion date.')
                continue
            if affected_week(options, week) and options.get('closure_location') in a['footprint']:
                reasons[aid]['Closure intersects work or exclusion buffer'] += 1
                blocked(aid,'closure',week,None,'The simulated closure intersects this activity’s work or safety footprint.',locations=[options['closure_location']])
                continue
            choices = []
            for night in range(1, 8):
                peers = slots[week, night]
                budget = budgets[cid, a['activity_type'], week]
                if night not in budget and len(budget) >= p['number_of_maximum_access_per_week']:
                    reasons[aid]['Contract weekly access limit'] += 1
                    blocked(aid,'weekly_budget',week,night,f'{cid} already uses its {p["number_of_maximum_access_per_week"]} granted nights this week.')
                    continue
                if sum(r['contract_number'] == cid and r['activity_type'] == a['activity_type'] for r in peers) >= p['number_of_workfronts']:
                    reasons[aid]['Concurrent workfront limit'] += 1
                    blocked(aid,'workfront',week,night,f'{cid} already uses its {p["number_of_workfronts"]} concurrent workfronts on this night.')
                    continue
                # CSV possessions are checked across the week. A different
                # internal dispatch night is not an exemption from another
                # possession's closure. Compatible overlapping jobs must be
                # placed together; incompatible jobs move to a different week.
                collision=next((r for r in rows if r['week']==week and (
                    collides(aid,r['activity_id']) if r['night']==night else
                    bool(set(a['locations']) & set(acts[r['activity_id']]['footprint']) or
                         set(a['footprint']) & set(acts[r['activity_id']]['locations'])))),None)
                if collision:
                    reasons[aid]['Possession, buffer or live-rail conflict'] += 1
                    other=acts[collision['activity_id']]
                    shared=sorted(set(a['footprint']) & set(other['footprint']))
                    rule='Live closure (including opposite-bound/interchange isolation)' if 'Live' in (a['nature'],other['nature']) else 'Incompatible possession or overlapping safety buffers'
                    blocked(aid,'collision',week,night,f'{rule}: {other["activity_id"]} ({other["contract_number"]}) holds a possession this week.',other['activity_id'],shared)
                    continue
                full=[loc for loc in a['locations'] if sum(loc in acts[r['activity_id']]['locations'] for r in peers)>=4]
                if full:
                    reasons[aid]['Four-party co-sharing limit']+=1
                    blocked(aid,'mix',week,night,'This location already has four work parties in its shared possession.',locations=full)
                    continue
                exhausted=[loc for loc in a['locations'] if
                           (affected_week(options,week) and options.get('capacity_location')==loc and len(supply[week,loc] | {night})>options['capacity_nights']) or
                           (scenario!='B' and len(supply[week,loc] | {night})>capacity_at(instance,options,week,loc)+(scenario=='C'))]
                if exhausted:
                    reasons[aid]['Location weekly supply exhausted'] += 1
                    blocked(aid,'capacity',week,night,'No permitted access-night remains at the listed location(s). Compatible work may still co-share an occupied slot.',locations=exhausted)
                    continue
                team = []
                for role in ['Engineer', 'Technician']:
                    pool = [person for person in roster if person['role'] == role and skill(a) in person['skills'].split(';') and
                            available(person, week, options) and person['id'] not in crew_slot[week, night] and crew_week[week, person['id']] < person['max_shifts']]
                    if pool:
                        pool.sort(key=lambda person: (0 if target and person['id'] in target['crew_ids'] else 1, crew_week[week, person['id']], crew_total[person['id']], person['name']))
                        team.append(pool[0])
                if len(team) != 2:
                    reasons[aid]['Qualified crew unavailable'] += 1
                    blocked(aid,'crew',week,night,f'A qualified {skill(a)} Engineer and Technician were not both available within shift limits.')
                    continue
                excess = sum(night not in supply[week, loc] and len(supply[week, loc]) >= capacity_at(instance,options,week,loc) for loc in a['locations'])
                choices.append(((0 if target and (week, night) == (target['week'], target['night']) else 1, excess, night), night, team))
            if choices:
                _, night, team = min(choices, key=lambda x: x[0])
                eclo = int(scenario != 'A' and aid not in standard_only and not (options.get('no_eclo') and affected_week(options,week)) and remaining[aid] >= 3 and remaining[aid] > 2*max(0,p['deadline_week']-week+1))
                if eclo and scenario == 'C' and any(max(eclo_weeks[line] | {week})-min(eclo_weeks[line] | {week}) > 1 for line in a['affected_lines']): eclo = 0
                commit(a, week, night, team, eclo)
        if not any(remaining.values()): break
    activities = []
    weighted = 0
    for aid, a in acts.items():
        deadline = instance['projects'][a['contract_number']]['planned_completion_date']
        completion = week_end(instance, finished[aid]) if aid in finished else None
        delay = max(0, (date.fromisoformat(completion)-date.fromisoformat(deadline)).days) if completion else None
        weighted += (delay or 0)*{1:100,2:10,3:1}[a['contract_priority']]*{1:1.3,2:1.2,3:1}[a['activity_priority']]
        activities.append(dict(a, accesses=assigned[aid], completion_week=finished.get(aid), completion_date=completion,
                               deadline=deadline, overrun_days=delay, remaining_workload=remaining[aid]/2, reasons=[x for x,_ in reasons[aid].most_common(3)],blockers=list(blockers[aid].values())))
    contracts=[]
    for cid,p in instance['projects'].items():
        jobs=[a for a in activities if a['contract_number']==cid]
        completion=max(a['completion_date'] for a in jobs) if jobs and all(a['completion_date'] for a in jobs) else None
        delay=max(0,(date.fromisoformat(completion)-date.fromisoformat(p['planned_completion_date'])).days) if completion else None
        contracts.append(dict(contract_number=cid,description=p['contract_description'],priority=p['contract_priority'],completion_date=completion,
                              planned_completion_date=p['planned_completion_date'],overrun_days=delay,status='Incomplete' if completion is None else 'Late' if delay else 'On plan'))
    excess=sum(max(0,len(nights)-capacity_at(instance,options,w,loc)) for (w,loc),nights in supply.items())
    changed=access_changes(reference['accesses'],rows) if reference else 0
    metrics=dict(accesses=len(rows),last_week=max((r['week'] for r in rows),default=0),remaining_workload=sum(remaining.values())/2,
                 late_contracts=sum(c['status']=='Late' for c in contracts),overrun_days=sum(c['overrun_days'] or 0 for c in contracts),
                 eclo_nights=sum(r['eclo'] for r in rows),excess_nights=excess,changed_accesses=changed,
                 objective=round((0 if scenario=='B' else weighted)+(0 if scenario=='A' else 7*excess+5*sum(r['eclo'] for r in rows)),2))
    plan=dict(scenario=scenario,options=options,accesses=rows,activities=activities,contracts=contracts,metrics=metrics,planner_version=PLANNER_VERSION,
              method='Three-order greedy heuristic; optimality is not guaranteed.',
              assumptions=['One qualified Engineer and one Technician per activity-night; fictional crew.',
                           'One shift per person per night, with weekly limits and leave weeks.',
                           'Live work uses conservative exclusive buffers. Supply repeats each week; search stops at week 104.',
                           'Local audit only; the organisers’ reference validator is not included.'])
    plan['audit']=audit(instance,roster,plan)
    return plan


def audit(instance, roster, plan):
    acts={a['activity_id']:a for a in instance['activities']}; people={p['id']:p for p in roster}
    violations=[]; by_a=defaultdict(list); by_slot=defaultdict(list); supply=defaultdict(set); budgets=defaultdict(set)
    person_slots=Counter(); person_weeks=Counter(); line_eclo=defaultdict(set)
    scenario=plan['scenario']; options=plan.get('options',{})
    def fail(rule,detail): violations.append(dict(rule=rule,detail=detail))
    for r in plan['accesses']:
        a=acts[r['activity_id']]; w,n=r['week'],r['night']; by_a[a['activity_id']].append(r); by_slot[w,n].append(r)
        if w<a['start_week']: fail('start',a['activity_id'])
        if affected_week(options,w) and options.get('closure_location') in a['footprint']: fail('closure',a['activity_id'])
        if r['eclo']:
            if scenario=='A': fail('eclo',a['activity_id'])
            if options.get('no_eclo') and affected_week(options,w): fail('eclo_restriction',a['activity_id'])
            for line in a['affected_lines']: line_eclo[line].add(w)
        if len(r['crew_ids'])!=2 or {people.get(pid,{}).get('role') for pid in r['crew_ids']}!={'Engineer','Technician'}: fail('crew_roles',a['activity_id'])
        for pid in r['crew_ids']:
            p=people.get(pid)
            if not p or not available(p,w,options) or skill(a) not in p['skills'].split(';'): fail('crew_availability',f'{a["activity_id"]}, week {w}')
            person_slots[pid,w,n]+=1; person_weeks[pid,w]+=1
        for loc in a['locations']: supply[w,loc].add(n)
        budgets[a['contract_number'],a['activity_type'],w].add(n)
    for aid,a in acts.items():
        rows=by_a[aid]
        if sum(1.5 if r['eclo'] else 1 for r in rows)<a['total_accesses']: fail('workload',f'{aid}: workload not fully scheduled')
        if len({r['week'] for r in rows})!=len(rows): fail('weekly_activity',aid)
        pred=a['predecessor_activity_id']
        if rows and pred and (not by_a[pred] or min(r['week'] for r in rows)<=max(r['week'] for r in by_a[pred])): fail('precedence',aid)
        if scenario=='B' and rows and week_end(instance,max(r['week'] for r in rows))>instance['projects'][a['contract_number']]['planned_completion_date']: fail('deadline',aid)
    for (w,n),rows in by_slot.items():
        for x,y in combinations(rows,2):
            if conflict(acts[x['activity_id']],acts[y['activity_id']]): fail('collision',f'Week {w}, night {n}: {x["activity_id"]} / {y["activity_id"]}')
        for loc in instance['supply']:
            if sum(loc in acts[r['activity_id']]['locations'] for r in rows)>4: fail('mix',f'{loc}, week {w}')
        counts=Counter((r['contract_number'],r['activity_type']) for r in rows)
        for (cid,_),count in counts.items():
            if count>instance['projects'][cid]['number_of_workfronts']: fail('workfront',cid)
    for (cid,_,w),nights in budgets.items():
        if len(nights)>instance['projects'][cid]['number_of_maximum_access_per_week']: fail('weekly_budget',f'{cid}, week {w}')
    for (w,loc),nights in supply.items():
        if scenario!='B' and len(nights)>capacity_at(instance,options,w,loc)+(scenario=='C'): fail('capacity',f'{loc}, week {w}')
        if affected_week(options,w) and options.get('capacity_location')==loc and len(nights)>options['capacity_nights']: fail('capacity_reduction',f'{loc}, week {w}')
    for (pid,w,n),count in person_slots.items():
        if count>1: fail('crew_double_booking',f'{pid}, week {w}, night {n}')
    for (pid,w),count in person_weeks.items():
        if pid in people and count>people[pid]['max_shifts']: fail('crew_limit',f'{people[pid]["name"]}, week {w}')
    if scenario=='C':
        for line,weeks in line_eclo.items():
            if max(weeks)-min(weeks)>1: fail('eclo_window',line)
    # Validate what the judge receives, independently of internal night slots.
    from .submission import closure_violations, tables
    violations.extend(closure_violations(instance,tables(instance,plan)['SCHEDULE_OCCUPANCY.csv']))
    return dict(passed=not violations,violations=violations,checked_accesses=len(plan['accesses']),official_validator=False,
                checks=['Full workload','Start dates and predecessor order','Exclusion buffers and legal mixes','Exported weekly possession-group closures','Location supply','Weekly contract budgets and workfronts','ECLO policy','Crew skills, leave, weekly limits and double bookings','Disruption closures, capacity reductions and ECLO restrictions'])


def forecast(instance, roster, baseline, options):
    candidate=generate(instance,roster,baseline['scenario'],options,baseline)
    changes=[]; direct=set()
    for row in baseline['accesses']:
        a=next(a for a in instance['activities'] if a['activity_id']==row['activity_id'])
        if affected_week(options,row['week']) and (options.get('closure_location') in a['footprint'] or options.get('capacity_location') in a['locations'] or (options.get('no_eclo') and row['eclo']) or set(row['crew_ids']) & set(options.get('absent_ids',[]))): direct.add(a['activity_id'])
    before={a['activity_id']:a for a in baseline['activities']}
    for a in candidate['activities']:
        b=before[a['activity_id']]
        signature=lambda x:[(r['week'],r['night'],r['crew_ids'],r['eclo']) for r in x['accesses']]
        if signature(a)!=signature(b):
            delay=max(0,(a['completion_week']-b['completion_week'])*7) if a['completion_week'] and b['completion_week'] else None
            changes.append(dict(activity_id=a['activity_id'],contract_number=a['contract_number'],priority=a['contract_priority'],before=b['completion_date'],after=a['completion_date'],delay_days=delay,
                                reason='Direct disruption / access restriction' if a['activity_id'] in direct else 'Dependency or shared-resource reallocation'))
    band='Critical' if candidate['metrics']['remaining_workload'] else 'High' if any(c['priority']==1 and c['delay_days'] for c in changes) else 'Watch' if any(c['delay_days'] for c in changes) else 'Low'
    return dict(risk_band=band,directly_affected=len(direct),changed_activities=changes,max_delay_days=max((c['delay_days'] or 0 for c in changes),default=0),
                additional_overrun_days=max(0,candidate['metrics']['overrun_days']-baseline['metrics']['overrun_days']),candidate=candidate,
                explanation='Deterministic what-if simulation, not a probability of equipment failure. Past weeks are frozen; future work is replanned.')
