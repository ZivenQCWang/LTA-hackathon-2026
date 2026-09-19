"""Check real export bytes and deliberately invalid Scenario C submissions."""
from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
import hashlib

import pytest

from backend.database import DEMO_NAMES
from backend.domain import OFFICIAL, csv_rows, csv_text, load_official, prepare
from backend.insights import explain_issue
from backend.planner import generate
from backend.submission import HEADERS, tables, validate_csv_content


@pytest.fixture(scope='module')
def setup():
    inst=prepare(load_official())
    roster=[dict(id=str(i),name=n,role='Engineer' if i%2==0 else 'Technician',
                 skills='track;construction;consist;electrical' if i%3==0 else 'track;construction;consist',
                 max_shifts=3,unavailable='',active=True) for i,n in enumerate(DEMO_NAMES)]
    plans={s:generate(inst,roster,s) for s in 'ABC'}
    exports={s:{n:csv_text(rows,HEADERS[n]) for n,rows in tables(inst,p).items()} for s,p in plans.items()}
    return inst,plans,exports


def replace_rows(content,name,rows):
    return dict(content,**{name:csv_text(rows,HEADERS[name])})


@pytest.mark.parametrize('scenario','ABC')
def test_complete_exports_have_independently_reconciled_scores(setup,scenario):
    inst,plans,exports=setup
    result=validate_csv_content(inst,exports[scenario])
    assert result['passed'],result['violations']
    assert result['workload_percent']==100
    assert result['activities_completed']==result['activities_total']==54
    assert result['objective']==plans[scenario]['metrics']['objective']
    assert not result['official_validator']


def test_b_csv_bytes_match_the_submission_accepted_by_the_organiser(setup):
    # User's portal screenshot: Feasible, score 30, zero overruns/excess, 6 ECLO.
    expected={
        'SCHEDULE_ACCESS.csv':'49f687509e3583860ab3d8fca824f4c6cab910dd08de2d60d6a11d2acc53e60c',
        'SCHEDULE_OCCUPANCY.csv':'66f6db7ab38797d45367fc91815394c49d3f356bc939609360eb84b59e13ea7e',
        'RESULTS.csv':'e587f5cce889103e8fe029cd7e3ca685d1e36699dd407751aded7803035cde88',
    }
    assert {name:hashlib.sha256(text.encode()).hexdigest() for name,text in setup[2]['B'].items()}==expected


def test_official_sample_passes_the_full_csv_checker(setup):
    content={name:(OFFICIAL/'03_submission_sample'/name).read_text() for name in HEADERS}
    result=validate_csv_content(setup[0],content)
    assert result['passed'],result['violations']


def test_c_search_reduces_optional_eclo_cost_without_relaxing_rules(setup):
    plan=setup[1]['C']; trace=plan['search']
    assert plan['audit']['passed'] and plan['metrics']['remaining_workload']==0
    assert plan['metrics']['objective']<=26.1
    assert plan['metrics']['eclo_nights']==2
    assert trace['evaluated']>3
    assert min(c['objective'] for c in trace['candidates'][:3] if not c['remaining'] and not c['violations'])==29.1
    assert all('standard nights' in c['order'] for c in trace['candidates'][3:])


def test_c_explains_its_unavoidable_workload_window(setup):
    inst,plans,_=setup
    a=next(a for a in plans['C']['activities'] if a['activity_id']=='A036')
    issue=explain_issue(inst,a,'C')
    assert issue['blockers'][0]['rule']=='workload_window'
    assert 'week 27' in issue['blockers'][0]['detail']
    assert 'target is week 26' in issue['blockers'][0]['detail']
    assert 'at most two ECLO' in issue['blockers'][0]['detail']


def test_c_rejects_ecLo_outside_the_two_week_span_including_cross_line_live(setup):
    inst,_,exports=setup; content=exports['C']
    rows=csv_rows(content['SCHEDULE_ACCESS.csv'])
    live=next(r for r in rows if r['activity_id']=='A074')
    live['eclo']='1'  # Interchange Live ECLO affects both Alpha and Beta windows.
    result=validate_csv_content(inst,replace_rows(content,'SCHEDULE_ACCESS.csv',rows))
    assert not result['passed'] and result['objective'] is None
    assert any(v['rule']=='eclo_window' and 'BET' in v['detail'] for v in result['violations'])


def test_c_allows_one_excess_location_night_and_rejects_two(setup):
    inst,_,exports=setup; content=exports['C']; changed=deepcopy(inst)
    rows=csv_rows(content['SCHEDULE_OCCUPANCY.csv']); groups=defaultdict(list)
    for r in rows:groups[r['week'],r['location_id']].append(r)
    (week,location),shared=next((key,rs) for key,rs in groups.items() if len(rs)>1)
    changed['supply'][location]=0
    allowed=validate_csv_content(changed,content)
    assert allowed['passed'],allowed['violations']
    assert allowed['excess_nights']>0
    shared[0]['co_share_group']='another-possession'
    invalid=validate_csv_content(changed,replace_rows(content,'SCHEDULE_OCCUPANCY.csv',rows))
    assert any(v['rule']=='capacity' and f'week {week}:' in v['detail'] for v in invalid['violations'])


def test_c_cannot_claim_full_work_with_missing_accesses(setup):
    inst,_,exports=setup; content=exports['C']
    rows=[r for r in csv_rows(content['SCHEDULE_ACCESS.csv']) if r['activity_id']!='A036']
    result=validate_csv_content(inst,replace_rows(content,'SCHEDULE_ACCESS.csv',rows))
    assert result['workload_percent']<100 and result['activities_completed']==53
    assert any(v['rule']=='workload' for v in result['violations'])


def test_csv_checker_recomputes_result_dates_instead_of_trusting_them(setup):
    inst,_,exports=setup; content=exports['C']
    rows=csv_rows(content['RESULTS.csv'])
    rows[0]['simulated_completion_date']=str(date.fromisoformat(rows[0]['simulated_completion_date'])+timedelta(days=7))
    result=validate_csv_content(inst,replace_rows(content,'RESULTS.csv',rows))
    assert any(v['rule']=='results' for v in result['violations'])


def test_c_cannot_be_relabelled_b_to_bypass_fixed_deadlines(setup):
    inst,_,exports=setup; content=exports['C']
    rows=csv_rows(content['RESULTS.csv'])
    for r in rows:r['scenario']='B'
    result=validate_csv_content(inst,replace_rows(content,'RESULTS.csv',rows))
    assert any(v['rule']=='planned_date' for v in result['violations'])


def test_csv_checker_rejects_duplicate_results_and_changed_headers(setup):
    inst,_,exports=setup; content=exports['C']
    rows=csv_rows(content['RESULTS.csv']);rows.append(dict(rows[0]))
    assert not validate_csv_content(inst,replace_rows(content,'RESULTS.csv',rows))['passed']
    invalid=dict(content,**{'SCHEDULE_ACCESS.csv':content['SCHEDULE_ACCESS.csv'].replace('access_night','calendar_night',1)})
    assert validate_csv_content(inst,invalid)['violations'][0]['rule']=='schema'
