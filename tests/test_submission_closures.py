"""Regression against the user's actual rejected CSVs and organiser sample.

No official portal requests: these tests do not spend submission attempts.
"""
import json
from pathlib import Path

import pytest

from backend.domain import OFFICIAL, csv_rows, load_official, prepare
from backend.submission import closure_violations, inspect_submission

FIXTURE = Path(__file__).parent / 'fixtures' / 'rejected_scenario_a'


@pytest.fixture(scope='module')
def instance():
    return prepare(load_official())


def test_reproduces_every_officially_reported_closure_error(instance):
    occupancy=csv_rows((FIXTURE/'SCHEDULE_OCCUPANCY.csv').read_text())
    actual=closure_violations(instance,occupancy)
    expected=json.loads((FIXTURE/'reported_closures.json').read_text())
    assert len(actual)==len(expected)==49
    assert {v['detail'] for v in actual}=={
        f'wk{week}: {aid} inside closure of {members} at {locations}'
        for week,aid,members,locations in expected
    }


def test_official_sample_has_no_closure_violations(instance):
    occupancy=csv_rows((OFFICIAL/'03_submission_sample'/'SCHEDULE_OCCUPANCY.csv').read_text())
    assert closure_violations(instance,occupancy)==[]


def test_different_night_labels_do_not_hide_weekly_closures(instance):
    # Both co-workers touch S15; merely giving them different calendar nights
    # caused the first pair of official errors. Shared possession is legal.
    acts={a['activity_id']:a for a in instance['activities']}
    rows=[dict(activity_id=aid,week=8,location_id=loc,co_share_group=group)
          for aid,group in [('A037','n2'),('A061','n1')]
          for loc in acts[aid]['locations']]
    assert len(closure_violations(instance,rows))==2
    for row in rows: row['co_share_group']='together'
    assert closure_violations(instance,rows)==[]


def test_live_interchange_buffer_reaches_both_lines(instance):
    acts={a['activity_id']:a for a in instance['activities']}
    live=acts['A074']
    assert {'PLAT:BET:S13:WB','PLAT:BET:S16:EB','PLAT:ALP:S06:WB'} <= set(live['footprint'])
    consist=acts['A025']
    assert 'SEC:ALP:S03_S04:EB' in consist['footprint']
    assert 'PLAT:ALP:S04:EB' not in consist['footprint']


def test_export_inspection_rejects_stale_passed_flag(instance):
    accesses=csv_rows((FIXTURE/'SCHEDULE_ACCESS.csv').read_text())
    occupancy=csv_rows((FIXTURE/'SCHEDULE_OCCUPANCY.csv').read_text())
    nights={(r['activity_id'],int(r['week'])):int(r['co_share_group'][1:]) for r in occupancy}
    acts={a['activity_id']:a for a in instance['activities']}
    rows=[dict(activity_id=r['activity_id'],week=int(r['week']),access_seq=int(r['access_seq']),
               eclo=int(r['eclo']),night=nights[r['activity_id'],int(r['week'])],
               contract_number=acts[r['activity_id']]['contract_number'],activity_type=acts[r['activity_id']]['activity_type'])
          for r in accesses]
    contracts=[dict(contract_number=r['contract_number'],completion_date=r['simulated_completion_date'],overrun_days=int(r['overrun_days']))
               for r in csv_rows((FIXTURE/'RESULTS.csv').read_text())]
    report=inspect_submission(instance,dict(scenario='A',accesses=rows,contracts=contracts,audit={'passed':True}))
    assert not report['passed']
    assert len(report['violations'])==49


def test_legacy_saved_plan_is_rebuilt_with_its_restrictions(instance,monkeypatch):
    from backend import main
    from backend.database import DEMO_NAMES
    from backend.planner import PLANNER_VERSION
    roster=[dict(id=str(i),name=name,role='Engineer' if i%2==0 else 'Technician',
                 skills='track;construction;consist;electrical',max_shifts=3,
                 unavailable='',active=True) for i,name in enumerate(DEMO_NAMES)]
    restrictions=dict(week=11,duration=2,closure_location='SEC:BET:H01_H02:EB')
    legacy=dict(revision='unchanged-inputs',audit={'passed':True},options=restrictions)
    monkeypatch.setattr(main,'instance',lambda:instance)
    monkeypatch.setattr(main,'people',lambda:roster)
    monkeypatch.setattr(main,'revision',lambda:'unchanged-inputs')
    monkeypatch.setattr(main,'get_setting',lambda key:legacy)
    monkeypatch.setattr(main,'cache',{})
    rebuilt=main.baseline('A')
    assert rebuilt is not legacy
    assert rebuilt['planner_version']==PLANNER_VERSION
    assert rebuilt['options']==restrictions
    assert rebuilt['audit']['passed']
    assert inspect_submission(instance,rebuilt)['passed']
