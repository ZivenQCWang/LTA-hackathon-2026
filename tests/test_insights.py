"""Decision-support regressions using organiser data; never package or submit a ZIP."""
from collections import defaultdict
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from backend import main
from backend.database import DEMO_NAMES, get_setting
from backend.domain import conflict, load_official, prepare
from backend.insights import analyse, brief, comparison, score_breakdown
from backend.planner import access_changes, audit, forecast, generate
from backend.submission import HEADERS, inspect_submission, tables


@pytest.fixture(scope='module')
def setup():
    inst=prepare(load_official())
    roster=[dict(id=str(i),name=name,role='Engineer' if i%2==0 else 'Technician',
                 skills='track;construction;consist;electrical' if i%3==0 else 'track;construction;consist',
                 max_shifts=3,unavailable='',active=True,demo=True) for i,name in enumerate(DEMO_NAMES)]
    return inst,roster,{s:generate(inst,roster,s) for s in 'ABC'}


def test_live_mirrors_both_bounds_and_only_live_crosses_interchange(setup):
    inst,_,_=setup
    crossed=0
    for a in inst['activities']:
        if a['nature']=='Live':
            assert all(loc[:-2]+('WB' if loc.endswith('EB') else 'EB') in a['footprint'] for loc in a['footprint'])
            if len(a['affected_lines'])==2:
                crossed+=1
                assert all(f'SEC:{line}:H01_H02:{bound}' in a['footprint'] for line in ['ALP','BET'] for bound in ['EB','WB'])
        else:
            assert a['affected_lines']==[a['line']]
            assert all(loc.split(':')[1]==a['line'] and loc.endswith(a['bound']) for loc in a['footprint'])
    assert crossed>0


@pytest.mark.parametrize('left,right,allowed',[('C','C',True),('PC','C',True),('C','PC',True),('PC','PC',False),('PM','C',False),('PM','PC',False),('PM','PM',False)])
def test_legal_co_sharing_pairs(left,right,allowed):
    a=dict(locations=['site'],footprint=['buffer','site'],access_type=left,nature='Non-live (Consist)')
    b=dict(a,access_type=right)
    assert conflict(a,b) is not allowed
    assert conflict(dict(a,nature='Live'),b)
    assert conflict(a,dict(b,locations=['next'],footprint=['buffer','next']))


def test_audit_detects_weekly_limits_workfronts_and_precedence(setup):
    inst,roster,plans=setup
    restricted=deepcopy(inst)
    for p in restricted['projects'].values():
        p['number_of_maximum_access_per_week']=0
        p['number_of_workfronts']=0
    rules={v['rule'] for v in audit(restricted,roster,plans['A'])['violations']}
    assert {'weekly_budget','workfront'}<=rules
    plan=deepcopy(plans['A'])
    successor=next(a for a in inst['activities'] if a['predecessor_activity_id'])
    pred_last=max(r['week'] for r in plan['accesses'] if r['activity_id']==successor['predecessor_activity_id'])
    next(r for r in plan['accesses'] if r['activity_id']==successor['activity_id'])['week']=pred_last
    assert 'precedence' in {v['rule'] for v in audit(inst,roster,plan)['violations']}


@pytest.mark.parametrize('scenario','ABC')
def test_capacity_reduction_is_hard_even_when_extra_access_is_allowed(setup,scenario):
    inst,roster,plans=setup; base=plans[scenario]
    a=next(a for a in base['activities'] if any(r['week']==11 for r in a['accesses']))
    loc=next(loc for loc in a['locations'] if inst['supply'][loc]>0)
    options=dict(capacity_location=loc,capacity_nights=0,week=11,duration=2)
    result=forecast(inst,roster,base,options); candidate=result['candidate']
    acts={a['activity_id']:a for a in inst['activities']}
    assert result['directly_affected']>0
    assert all(loc not in acts[r['activity_id']]['locations'] for r in candidate['accesses'] if 11<=r['week']<13)
    assert [r for r in candidate['accesses'] if r['week']<11]==[r for r in base['accesses'] if r['week']<11]
    assert not any(v['rule']=='capacity_reduction' for v in candidate['audit']['violations'])
    invalid=dict(base,options=options)
    assert any(v['rule']=='capacity_reduction' for v in audit(inst,roster,invalid)['violations'])


def test_no_eclo_freezes_history_and_preserves_full_workload_when_feasible(setup):
    inst,roster,plans=setup; base=plans['C']
    week=min(r['week'] for r in base['accesses'] if r['eclo'])
    options=dict(no_eclo=True,week=week,duration=2)
    f=forecast(inst,roster,base,options)
    assert f['directly_affected']>0
    assert all(not r['eclo'] for r in f['candidate']['accesses'] if week<=r['week']<week+2)
    assert f['candidate']['audit']['passed']
    assert f['candidate']['metrics']['remaining_workload']==0
    assert any(v['rule']=='eclo_restriction' for v in audit(inst,roster,dict(base,options=options))['violations'])


def test_churn_counts_removed_added_and_eclo_changes():
    row=dict(activity_id='A001',access_seq=1,week=1,night=1,crew_ids=['a','b'],eclo=0)
    assert access_changes([row],[])==1
    assert access_changes([],[row])==1
    assert access_changes([row],[dict(row,eclo=1)])==1
    assert access_changes([row],[dict(row,crew_ids=['b','a'])])==0


def test_scores_and_comparisons_reconcile_with_actual_plans(setup):
    inst,roster,plans=setup
    report=comparison(inst,roster,plans,'A')
    for p in plans.values():
        score=score_breakdown(p)
        assert score['eligible']
        assert score['total']==pytest.approx(score['delay']+score['extra_access']+score['eclo'])
        assert p['search']['evaluated']==len(p['search']['candidates'])
        assert p['search']['evaluated']>=3
        assert sum(c['selected'] for c in p['search']['candidates'])==1
    assert report['same_conditions']
    for issue in report['details']['issues']:
        assert issue['blockers']
        for alternative in issue['alternatives']:
            other=next(a for a in plans[alternative['scenario']]['activities'] if a['activity_id']==issue['activity_id'])
            assert alternative['completion_date']==other['completion_date']
    altered={s:dict(p,options={'no_eclo':True} if s!='A' else {}) for s,p in plans.items()}
    assert not comparison(inst,roster,altered,'A')['same_conditions']
    assert not any(i['alternatives'] for i in comparison(inst,roster,altered,'A')['details']['issues'])


def test_ecLo_exposure_deduplicates_line_nights_and_does_not_claim_demand(setup):
    inst,roster,plans=setup; plan=plans['B']; info=analyse(inst,roster,plan)
    acts={a['activity_id']:a for a in plan['activities']}
    expected={(line,r['week'],r['night']) for r in plan['accesses'] if r['eclo'] for line in acts[r['activity_id']]['affected_lines']}
    assert info['passenger']['eclo_line_nights']==len(expected)
    assert info['passenger']['has_demand_data'] is False
    assert sum(p['total'] for p in info['crew'])==2*len(plan['accesses'])
    assert info['co_shared_shifts']>0
    assert all(c['scheduled_percent']==100 for c in info['contracts'])


def test_csv_roundtrip_exact_headers_and_detects_missing_work_without_packaging(setup):
    inst,_,plans=setup
    for plan in plans.values():
        report=inspect_submission(inst,plan)
        assert report['passed'] and not report['official_validator'] and not report['packaged']
        assert {f['name']:f['columns'] for f in report['files']}==HEADERS
        assert set(tables(inst,plan))==set(HEADERS)
    damaged=dict(plans['A'],accesses=plans['A']['accesses'][1:])
    assert not inspect_submission(inst,damaged)['passed']


def test_handover_uses_actual_assignments_and_flags_unconfirmed_passenger_details(setup):
    inst,_,plans=setup; row=next(r for r in plans['B']['accesses'] if r['eclo'])
    ops=brief(inst,plans['B'],'contractor',row['week'],row['night'],row['contract_number'])
    assert ops['draft'] and row['activity_id'] in ops['text'] and row['crew_names'][0] in ops['text']
    passenger=brief(inst,plans['B'],'passenger',row['week'],row['night'])
    assert 'unconfirmed' in passenger['text'] and 'Synthetic' in passenger['text']
    assert 'does not imply' in brief(inst,plans['A'],'passenger',1,1)['text']


def test_api_insights_and_briefs_are_read_only_and_validate_filters():
    with TestClient(main.app) as client:
        before={s:get_setting('plan_'+s) for s in 'ABC'}
        assert client.get('/api/insights?scenario=A').status_code==200
        assert client.get('/api/brief?audience=operations&week=1&night=1').json()['draft']
        assert client.get('/api/brief?week=0').status_code==422
        assert client.get('/api/brief?contract=unknown').status_code==422
        assert before=={s:get_setting('plan_'+s) for s in 'ABC'}
        for payload in [dict(capacity_nights=1),dict(capacity_location='bad',capacity_nights=0),dict(capacity_location='SEC:BET:H01_H02:EB',capacity_nights=7)]:
            assert client.post('/api/risk',json=payload).status_code==422


def test_assistant_routes_quota_and_eclo_previews_without_inventing_a_closure(setup):
    inst,roster,_=setup
    intent=main.direct_intent('Simulate SEC:BET:H01_H02:EB capacity to 1 night in week 11 for 2 weeks.',inst,roster)
    assert intent.action=='forecast' and intent.capacity_nights==1 and intent.closure_location is None
    assert main.direct_intent('Simulate no ECLO in week 11 for 2 weeks.',inst,roster).no_eclo
    assert main.direct_intent('What if SEC:BET:H01_H02:EB loses half its capacity in week 11?',inst,roster) is None
