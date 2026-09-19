import copy
import csv
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from backend import main
from backend.domain import prepare, load_official
from backend.planner import generate, forecast, audit, leave_weeks
from backend.database import people, engine

client=TestClient(main.app)

def teardown_module():
    client.close()

@pytest.fixture(scope='module')
def inst(): return prepare(load_official())

@pytest.fixture(scope='module')
def plans(inst): return {s:generate(inst,people(),s) for s in 'ABC'}

def test_three_scenarios_conserve_work_and_have_distinct_policies(plans):
    for scenario,p in plans.items():
        assert p['audit']['passed'],p['audit']['violations']
        assert p['metrics']['remaining_workload']==0
        assert len(p['activities'])==54
        assert all(len(r['crew_ids'])==2 for r in p['accesses'])
    assert plans['A']['metrics']['excess_nights']==plans['A']['metrics']['eclo_nights']==0
    assert plans['B']['metrics']['late_contracts']==0
    assert plans['A']['accesses']!=plans['B']['accesses']

def test_closure_produces_delays_and_freezes_past(inst,plans):
    opts=dict(closure_location='SEC:BET:H01_H02:EB',week=11,duration=2,absent_ids=[])
    f=forecast(inst,people(),plans['A'],opts)
    assert f['directly_affected']>0 and f['max_delay_days']>0
    assert f['candidate']['audit']['passed']
    before=[r for r in plans['A']['accesses'] if r['week']<11]
    after=[r for r in f['candidate']['accesses'] if r['week']<11]
    assert before==after
    acts={a['activity_id']:a for a in inst['activities']}
    assert all(opts['closure_location'] not in acts[r['activity_id']]['footprint'] for r in f['candidate']['accesses'] if 11<=r['week']<13)

def test_named_absence_reassigns_crew(inst,plans):
    r=next(r for r in plans['A']['accesses'] if r['week']==11)
    f=forecast(inst,people(),plans['A'],dict(week=11,duration=1,absent_ids=r['crew_ids'],closure_location=None))
    assert f['directly_affected']>0
    assert all(not set(x['crew_ids'])&set(r['crew_ids']) for x in f['candidate']['accesses'] if x['week']==11)
    assert f['candidate']['audit']['passed']

def test_noop_disruption_does_not_invent_risk(inst,plans):
    f=forecast(inst,people(),plans['A'],dict(week=90,duration=1,closure_location='SEC:BET:H01_H02:EB',absent_ids=[]))
    assert f['risk_band']=='Low' and not f['changed_activities'] and f['max_delay_days']==0

def test_missing_qualified_crew_leaves_explicit_incomplete_work(inst):
    roster=copy.deepcopy(people())
    for p in roster: p['skills']='track;construction;consist'
    plan=generate(inst,roster)
    assert plan['metrics']['remaining_workload']>0
    assert not plan['audit']['passed']
    assert any(v['rule']=='workload' for v in plan['audit']['violations'])

def test_audit_detects_bad_workload_double_booking_and_eclo(inst,plans):
    p=copy.deepcopy(plans['A']); row=copy.deepcopy(p['accesses'][0]);p['accesses'].append(row);p['accesses'][0]['eclo']=1
    rules={v['rule'] for v in audit(inst,people(),p)['violations']}
    assert {'crew_double_booking','eclo','weekly_activity'}<=rules
    p=copy.deepcopy(plans['A']); p['accesses']=p['accesses'][1:]
    assert 'workload' in {v['rule'] for v in audit(inst,people(),p)['violations']}

def test_leave_validation():
    assert leave_weeks('5, 8,12-14')=={5,8,12,13,14}
    for value in ['0','105','8-3','next week']:
        with pytest.raises(ValueError): leave_weeks(value)

def test_api_export_schema():
    response=client.get('/api/export?scenario=A');assert response.status_code==200
    z=zipfile.ZipFile(io.BytesIO(response.content))
    assert set(z.namelist())=={'SCHEDULE_ACCESS.csv','SCHEDULE_OCCUPANCY.csv','RESULTS.csv'}
    accesses=list(csv.DictReader(io.StringIO(z.read('SCHEDULE_ACCESS.csv').decode())))
    assert len(accesses)==192 and set(accesses[0])=={'activity_id','access_seq','week','eclo','access_night'}
    assert all(1<=int(x['access_night'])<=3 for x in accesses)

def test_api_forecast_apply_and_reject_stale():
    client.post('/api/plan',json={'scenario':'A'})
    f=client.post('/api/risk',json={'week':11,'duration':2,'closure_location':'SEC:BET:H01_H02:EB'}).json()
    assert client.post('/api/runs/'+f['id']+'/apply',json={}).status_code==200
    assert client.get('/api/state').json()['plan']['options']['duration']==2
    assert client.post('/api/runs/'+f['id']+'/apply',json={}).status_code==409
    client.post('/api/plan',json={'scenario':'A'})

def test_roster_edit_persists_and_invalidates_forecast():
    response=client.post('/api/risk',json={'week':90,'closure_location':'SEC:BET:H01_H02:EB'})
    rid=response.json()['id']; roster=client.get('/api/people').json()['people']; person=roster[0]
    edited=dict(person,unavailable='5,8',max_shifts=2)
    assert client.put('/api/people/'+person['id'],json=edited).status_code==200
    saved=next(p for p in client.get('/api/people').json()['people'] if p['id']==person['id'])
    assert saved['max_shifts']==2 and saved['unavailable']=='5,8'
    assert client.post('/api/runs/'+rid+'/apply',json={}).status_code==409
    client.put('/api/people/'+person['id'],json=person)

def test_bulk_input_and_bad_leave():
    count=len(people())
    assert client.post('/api/people/bulk',json={'people':[{'name':'Fixture Person','role':'Engineer'}]}).status_code==200
    assert len(people())==count+1
    p=people()[0];p['unavailable']='tomorrow'
    assert client.put('/api/people/'+p['id'],json=p).status_code==422

def test_upload_rejects_missing_then_accepts_complete_instance():
    files=load_official()
    assert client.post('/api/instance',files=[('files',('bad.csv','hello','text/csv'))]).status_code==422
    response=client.post('/api/instance',files=[('files',(name,text,'text/csv')) for name,text in files.items()])
    assert response.status_code==200
    assert client.get('/api/state').json()['source']=='Uploaded instance'
    client.post('/api/instance/reset',json={})

def test_malformed_csv_keeps_current_instance():
    files=load_official()
    files['08_ACTIVITY_DETAILS.csv']+='A999,broken,row\n'
    response=client.post('/api/instance',files=[('files',(name,text,'text/csv')) for name,text in files.items()])
    assert response.status_code==422
    assert len(client.get('/api/state').json()['plan']['activities'])==54

def test_local_assistant_and_secret_free_state():
    response=client.post('/api/copilot',json={'message':'Who is assigned to A003?'}).json()
    assert response['model']=='Local planner' and 'A003' in response['response']
    state=client.get('/api/state').text
    assert 'sk-proj-' not in state and 'OPENAI_API_KEY' not in state

def test_cross_site_write_blocked():
    assert client.post('/api/plan',headers={'origin':'https://untrusted.example'},json={}).status_code==403

def test_ai_error_is_redacted(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-secret')
    def fail(): raise RuntimeError('test-secret provider error')
    monkeypatch.setattr(main,'client',fail)
    result=client.post('/api/copilot',json={'message':'Summarize the plan'}).json()
    assert result['model']=='Local planner' and 'test-secret' not in json.dumps(result)

def test_fully_specified_chat_closure_needs_no_crew(inst):
    intent=main.direct_intent('Simulate SEC:BET:H01_H02:EB closed in week 11 for 2 weeks.',inst,people())
    assert intent.action=='forecast' and intent.week==11 and intent.duration==2 and intent.absent_ids==[]
    assert main.direct_intent('Close H01-H02 in week 11',inst,people()) is None

def test_chat_named_absence_requires_no_location(inst):
    intent=main.direct_intent('Aisha Rahman is unavailable in week 11.',inst,people())
    assert intent.action=='forecast' and intent.closure_location is None
    assert intent.absent_ids==[p['id'] for p in people() if p['name']=='Aisha Rahman']
