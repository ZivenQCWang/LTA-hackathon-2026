"""Prepare and inspect PS1 CSV content without packaging or submitting it."""
from collections import defaultdict
from datetime import date
import csv
import io
from .domain import csv_text, csv_rows, week_end

HEADERS={
    'SCHEDULE_ACCESS.csv':['activity_id','access_seq','week','eclo','access_night'],
    'SCHEDULE_OCCUPANCY.csv':['activity_id','week','location_id','co_share_group'],
    'RESULTS.csv':['scenario','contract_number','simulated_completion_date','overrun_days'],
}


def closure_violations(instance, occupancy):
    """Check the weekly possession graph encoded in the exported CSV.

    Sharing at any (location, week, group) joins activities into one possession.
    Members are exempt from that possession's combined closure; external jobs
    are not, even if their internal calendar nights differ. This interpretation
    reproduces the 49 organiser-reported errors in our rejected Scenario A and
    reports no closure errors for the organiser's published sample. It is a
    local regression check, not the unpublished reference validator.
    """
    acts={a['activity_id']:a for a in instance['activities']}
    groups=defaultdict(set); weeks=defaultdict(set)
    for row in occupancy:
        aid=row['activity_id']; week=int(row['week'])
        groups[week,row['location_id'],row['co_share_group']].add(aid)
        weeks[week].add(aid)
    violations=[]
    for week,ids in sorted(weeks.items()):
        parent={aid:aid for aid in ids}
        def root(aid):
            while parent[aid]!=aid:
                parent[aid]=parent[parent[aid]]
                aid=parent[aid]
            return aid
        for (w,_,_),members in groups.items():
            if w!=week: continue
            members=sorted(members)
            for aid in members[1:]: parent[root(aid)]=root(members[0])
        possessions=defaultdict(set)
        for aid in sorted(ids): possessions[root(aid)].add(aid)
        for members in possessions.values():
            closure=set().union(*(acts[aid]['footprint'] for aid in members))
            for aid in sorted(ids-members):
                hit=sorted(set(acts[aid]['locations']) & closure)
                if hit:
                    violations.append(dict(rule='closure',detail=f'wk{week}: {aid} inside closure of {sorted(members)[:3]} at {hit[:4]}'))
    return violations


def tables(instance, plan):
    granted=defaultdict(set)
    for r in plan['accesses']: granted[r['contract_number'],r['activity_type'],r['week']].add(r['night'])
    activities={a['activity_id']:a for a in instance['activities']}
    access=[]; occupancy=[]
    for r in plan['accesses']:
        nights=sorted(granted[r['contract_number'],r['activity_type'],r['week']])
        access.append(dict(r,access_night=nights.index(r['night'])+1))
        for loc in activities[r['activity_id']]['locations']:
            occupancy.append(dict(activity_id=r['activity_id'],week=r['week'],location_id=loc,co_share_group=f'n{r["night"]}'))
    results=[dict(scenario=plan['scenario'],contract_number=c['contract_number'],simulated_completion_date=c['completion_date'],overrun_days=c['overrun_days']) for c in plan['contracts']]
    return dict(zip(HEADERS,[access,occupancy,results]))


CSV_CHECKS=['Exact filenames and CSV headers','Known activities, locations and contracts',
            'Full activity workload and one access per activity-week','Start dates and predecessor order',
            'Local contract/type/week access-night indices and weekly budgets','Workfront caps after index conversion',
            'Complete, unique occupancy rows','Legal possession mixes','Weekly possession-group closures after CSV conversion',
            'Scenario-specific location supply','ECLO policy and Scenario C two-week line windows',
            'Scenario B fixed deadlines','One scenario and exactly one result per contract',
            'Completion dates and overrun values recomputed from accesses']


def validate_csv_content(instance, content):
    """Validate the actual CSV text, without trusting plan metrics/audit flags.

    This checks the published output contract and our regression-tested closure
    model. It is not the organiser's unpublished reference validator.
    """
    parsed={}; violations=[]
    def fail(rule,detail): violations.append(dict(rule=rule,detail=detail))
    def report(**extra):
        return dict(passed=not violations,official_validator=False,violations=violations,
                    checks=CSV_CHECKS,files=[dict(name=n,columns=HEADERS[n],rows=len(rows)) for n,rows in parsed.items()],**extra)
    if set(content)!=set(HEADERS):
        fail('schema','Exactly the three required CSV filenames must be present.')
        return report()
    for name,text in content.items():
        try:
            if next(csv.reader(io.StringIO(text.lstrip('\ufeff'))),[])!=HEADERS[name]:
                raise ValueError('Headers do not match the required names and order.')
            parsed[name]=csv_rows(text)
        except (ValueError,csv.Error) as exc:
            fail('schema',f'{name}: {exc}')
    if violations: return report()
    acts={a['activity_id']:a for a in instance['activities']}
    accesses=parsed['SCHEDULE_ACCESS.csv']; occupancy=parsed['SCHEDULE_OCCUPANCY.csv']; results=parsed['RESULTS.csv']
    for name in ['SCHEDULE_ACCESS.csv','SCHEDULE_OCCUPANCY.csv']:
        for r in parsed[name]:
            if r['activity_id'] not in acts: fail('activity',f'Unknown activity {r["activity_id"]}.')
            try:
                r['week']=int(r['week'])
                if r['week']<1: raise ValueError()
                if name=='SCHEDULE_ACCESS.csv':
                    for field in ['access_seq','access_night','eclo']: r[field]=int(r[field])
                    if r['access_seq']<1 or r['access_night']<1 or r['eclo'] not in (0,1): raise ValueError()
            except ValueError: fail('value',f'{name}: invalid week, access index or ECLO value.')
            if name=='SCHEDULE_OCCUPANCY.csv' and (r['location_id'] not in instance['supply'] or not r['co_share_group']):
                fail('location','Unknown location or empty possession group.')
    scenarios={r['scenario'] for r in results}
    if len(scenarios)!=1 or not scenarios<=set('ABC'): fail('scenario','RESULTS.csv must contain exactly one scenario: A, B or C.')
    if violations: return report()
    scenario=next(iter(scenarios))
    workload=defaultdict(float); by_activity=defaultdict(list); workfronts=defaultdict(set); budgets=defaultdict(set); line_eclo=defaultdict(set)
    for r in accesses:
        a=acts[r['activity_id']]; p=instance['projects'][a['contract_number']]
        night=r['access_night']; w=r['week']
        if night>p['number_of_maximum_access_per_week']: fail('weekly_budget',f'{a["activity_id"]}: access_night outside granted range.')
        workload[a['activity_id']]+=1.5 if r['eclo'] else 1
        by_activity[a['activity_id']].append(r)
        workfronts[a['contract_number'],a['activity_type'],w,night].add(a['activity_id'])
        budgets[a['contract_number'],a['activity_type'],w].add(night)
        if w<a['start_week']: fail('start',a['activity_id'])
        if r['eclo']:
            if scenario=='A': fail('eclo','Scenario A forbids ECLO.')
            for line in a['affected_lines']: line_eclo[line].add(w)
    activity_completion={}
    for aid,a in acts.items():
        rows=by_activity[aid]; weeks=[r['week'] for r in rows]
        if workload[aid]<a['total_accesses']: fail('workload',f'{aid}: full workload is not represented.')
        if len(set(weeks))!=len(weeks): fail('weekly_activity',f'{aid}: more than one access in a week.')
        if sorted(r['access_seq'] for r in rows)!=list(range(1,len(rows)+1)): fail('access_seq',f'{aid}: access sequences must be unique and consecutive.')
        pred=a['predecessor_activity_id']
        if rows and pred and (not by_activity[pred] or min(weeks)<=max(r['week'] for r in by_activity[pred])): fail('precedence',aid)
        if rows:
            activity_completion[aid]=week_end(instance,max(weeks))
            if scenario=='B' and activity_completion[aid]>instance['projects'][a['contract_number']]['planned_completion_date']: fail('planned_date',aid)
    for (cid,_,week,_),ids in workfronts.items():
        if len(ids)>instance['projects'][cid]['number_of_workfronts']: fail('workfront',f'{cid}, week {week}: workfront cap exceeded.')
    for (cid,_,week),nights in budgets.items():
        if len(nights)>instance['projects'][cid]['number_of_maximum_access_per_week']: fail('weekly_budget',f'{cid}, week {week}.')
    expected={(aid,r['week'],loc) for aid,rows in by_activity.items() for r in rows for loc in acts[aid]['locations']}
    actual=[(r['activity_id'],r['week'],r['location_id']) for r in occupancy]
    if set(actual)!=expected or len(actual)!=len(set(actual)): fail('occupancy','Occupancy footprint is incomplete or duplicated.')
    groups=defaultdict(set); supply=defaultdict(set)
    for r in occupancy:
        groups[r['week'],r['location_id'],r['co_share_group']].add(r['activity_id'])
        supply[r['week'],r['location_id']].add(r['co_share_group'])
    for (week,loc,_),ids in groups.items():
        types=[acts[aid]['access_type'] for aid in ids]
        if len(ids)>4 or types.count('PC')>1 or ('PM' in types and len(ids)>1): fail('mix',f'{loc}, week {week}: illegal possession mix.')
    excess=0
    for (week,loc),possessions in supply.items():
        extra=max(0,len(possessions)-instance['supply'][loc]); excess+=extra
        if scenario!='B' and extra>(1 if scenario=='C' else 0): fail('capacity',f'{loc}, week {week}: {extra} excess access-nights.')
    if scenario=='C':
        for line,weeks in line_eclo.items():
            if max(weeks)-min(weeks)>1: fail('eclo_window',f'{line}: ECLO lies outside one two-week span.')
    violations.extend(closure_violations(instance,occupancy))
    if len(results)!=len(instance['projects']) or {r['contract_number'] for r in results}!=set(instance['projects']):
        fail('results','Exactly one result per contract is required.')
    for r in results:
        cid=r['contract_number']
        if cid not in instance['projects']: continue
        jobs=[aid for aid,a in acts.items() if a['contract_number']==cid]
        completion=max((activity_completion.get(aid,'') for aid in jobs),default='')
        try:
            overrun=max(0,(date.fromisoformat(completion)-date.fromisoformat(instance['projects'][cid]['planned_completion_date'])).days)
            if any(aid not in activity_completion for aid in jobs) or r['simulated_completion_date']!=completion or int(r['overrun_days'])!=overrun:
                raise ValueError()
        except ValueError: fail('results',f'{cid}: completion date or overrun does not match scheduled accesses.')
    weighted=sum(max(0,(date.fromisoformat(completion)-date.fromisoformat(instance['projects'][acts[aid]['contract_number']]['planned_completion_date'])).days)
                 *{1:100,2:10,3:1}[acts[aid]['contract_priority']]*{1:1.3,2:1.2,3:1}[acts[aid]['activity_priority']]
                 for aid,completion in activity_completion.items())
    eclo=sum(r['eclo'] for r in accesses)
    objective=round((weighted if scenario!='B' else 0)+(7*excess+5*eclo if scenario!='A' else 0),2)
    return report(scenario=scenario,activities_completed=sum(workload[aid]>=a['total_accesses'] for aid,a in acts.items()),
                  activities_total=len(acts),workload_percent=round(100*sum(min(workload[aid],a['total_accesses']) for aid,a in acts.items())/sum(a['total_accesses'] for a in acts.values()),2),
                  objective=objective if not violations else None,excess_nights=excess,eclo_nights=eclo,
                  eclo_weeks={line:sorted(weeks) for line,weeks in line_eclo.items()})


def inspect_submission(instance, plan):
    content={name:csv_text(rows,HEADERS[name]) for name,rows in tables(instance,plan).items()}
    result=validate_csv_content(instance,content)
    violations=[v['detail'] for v in result['violations']]
    if result.get('scenario')!=plan['scenario']: violations.append('Export scenario does not match the selected plan.')
    if result.get('objective') is not None and 'metrics' in plan and result['objective']!=plan['metrics']['objective']:
        violations.append('Exported score does not match the plan metrics.')
    return dict(result,passed=not violations and plan['audit']['passed'],packaged=False,violations=violations,
                explanation='Independent CSV round-trip checks and PLiZ local audit only. No ZIP was generated or uploaded. The organiser’s validator is not published in the repository.')
