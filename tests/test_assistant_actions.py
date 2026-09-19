import json
from datetime import date,timedelta
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from backend import main
from backend.assistant_commands import Intent
from backend.database import ChatRequest,Person,Run,Setting,Session,engine,initialise,people,get_setting
from backend.domain import load_official

@pytest.fixture(autouse=True)
def isolated_workspace(monkeypatch):
    assert 'pliz-tests-' in str(engine.url)
    with Session.begin() as session:
        for model in [ChatRequest,Run,Setting,Person]: session.execute(delete(model))
    initialise(); main.cache.clear()
    monkeypatch.setenv('OPENAI_API_KEY','test-key')

@pytest.fixture
def client():
    with TestClient(main.app) as client: yield client

def route(monkeypatch,**values):
    intent=Intent(**values)
    responses=SimpleNamespace(parse=lambda **kw:SimpleNamespace(output_parsed=intent,output_text=intent.model_dump_json(),usage=None),create=lambda **kw:SimpleNamespace(output_text='Read-only answer.',usage=None))
    monkeypatch.setattr(main,'client',lambda:SimpleNamespace(responses=responses))
    return responses

def post(client,message,**extra):
    response=client.post('/api/copilot',json=dict(message=message,**extra))
    assert response.status_code==200,response.text
    return response.json()

def test_add_people_receipt_persistence_and_idempotency(client,monkeypatch):
    route(monkeypatch,action='add_people',crew=[dict(name='Jamie Tan',role='Technician',skills=['track','construction'],max_shifts=2)])
    message='Add Jamie Tan as a technician with track and construction skills, 2 shifts per week.'
    result=post(client,message,request_id='add-request-001')
    assert result['receipt']['kind']=='add_people'
    assert len(people())==25
    person=next(p for p in people() if p['name']=='Jamie Tan')
    assert person['skills']=='construction;track' and person['max_shifts']==2
    assert post(client,message,request_id='add-request-001')==result
    assert len(people())==25
    assert client.get('/api/chat/add-request-001').json()['result']==result
    assert client.post('/api/copilot',json={'message':'Add another person','request_id':'add-request-001'}).status_code==409
    state=client.get('/api/state').json()
    assert state['plan']['audit']['passed'] and state['plan']['revision']==main.revision()

def test_missing_details_followup_and_duplicate_name(client,monkeypatch):
    route(monkeypatch,action='add_people',crew=[dict(name='Jamie Tan')])
    first=post(client,'Add Jamie Tan to the crew.')
    assert first['clarification'] and len(people())==24
    route(monkeypatch,action='add_people',crew=[dict(name='Jamie Tan',role='Engineer',skills=['track'])])
    second=post(client,'Engineer, qualified in track work.',reply_to=first['request_id'])
    assert second['receipt'] and len(people())==25
    duplicate=post(client,'Add Jamie Tan as an Engineer with track skills.')
    assert duplicate['clarification'] and len(people())==25

def test_update_changes_only_requested_fields_and_replans(client,monkeypatch):
    before=next(p for p in people() if p['name']=='Aisha Rahman')
    route(monkeypatch,action='update_person',crew=[dict(name='Aisha Rahman',unavailable='11-12')])
    result=post(client,'Mark Aisha Rahman on leave in weeks 11-12 and replan.')
    after=next(p for p in people() if p['name']=='Aisha Rahman')
    assert result['receipt']['kind']=='update_person'
    assert after==dict(before,unavailable='11-12')
    plan=main.baseline('A')
    assert plan['audit']['passed']
    assert all(before['id'] not in r['crew_ids'] for r in plan['accesses'] if r['week'] in (11,12))

def test_followup_question_cannot_accidentally_finish_pending_write(client,monkeypatch):
    route(monkeypatch,action='add_people',crew=[dict(name='Jamie Tan')])
    first=post(client,'Add Jamie Tan.')
    route(monkeypatch,action='add_people',crew=[dict(name='Jamie Tan',role='Engineer',skills=['track'])])
    result=post(client,'What skills should I choose?',reply_to=first['request_id'])
    assert not result.get('receipt') and len(people())==24

@pytest.mark.parametrize('message',['How do I add Jamie Tan?','Do not add Jamie Tan.','Should I add Jamie Tan?'])
def test_question_or_negation_cannot_execute_model_write(client,monkeypatch,message):
    route(monkeypatch,action='add_people',crew=[dict(name='Jamie Tan',role='Engineer',skills=['track'])])
    result=post(client,message)
    assert not result.get('receipt') and len(people())==24

def job(**overrides):
    return dict(contract_number='C001',start_location_id='PLAT:BET:H02:EB',end_location_id='PLAT:BET:H02:EB',total_accesses=1,planned_start_date='2027-05-17',activity_priority=2,**overrides)

def test_add_job_uses_working_copy_and_schedules_it(client,monkeypatch):
    originals=load_official()
    route(monkeypatch,action='add_activity',activity=job())
    result=post(client,'Add a job under C001 at Beta H02 eastbound platform in week 20 for one work unit.')
    assert result['receipt']['kind']=='add_activity'
    state=client.get('/api/state').json()
    assert len(state['plan']['activities'])==55 and state['plan']['audit']['passed']
    assert 'user-added' in state['source']
    assert load_official()==originals

def test_invalid_or_unplannable_job_is_atomic(client,monkeypatch):
    originals=load_official(); rev=main.revision()
    route(monkeypatch,action='add_activity',activity=job(predecessor_activity_id='A999'))
    result=post(client,'Add this job under C001 with predecessor A999.')
    assert result['action_error'] and main.revision()==rev and get_setting('instance') is None
    late_job=job(); late_job.update(total_accesses=200,planned_start_date=str(date(2027,1,4)+timedelta(weeks=103)))
    route(monkeypatch,action='add_activity',activity=late_job)
    result=post(client,'Add this 200-work-unit job starting in week 104.')
    assert result['action_error'] and get_setting('instance') is None and load_official()==originals

def test_apply_requires_active_current_matching_preview(client,monkeypatch):
    missing=post(client,'Apply this plan.')
    assert missing['clarification']
    preview=client.post('/api/risk',json={'scenario':'A','week':11,'duration':2,'closure_location':'SEC:BET:H01_H02:EB'}).json()
    wrong=post(client,'Apply this plan.',scenario='B',forecast_id=preview['id'])
    assert wrong['action_error'] and not main.baseline('B')['options']
    applied=post(client,'Apply this plan.',forecast_id=preview['id'],request_id='apply-request-1')
    assert applied['receipt']['kind']=='apply_forecast' and main.baseline('A')['options']['duration']==2
    assert post(client,'Apply this plan.',forecast_id=preview['id'],request_id='apply-request-1')==applied
    stale=post(client,'Apply this plan.',forecast_id=preview['id'])
    assert stale['action_error']

def test_edit_preserves_applied_disruption(client,monkeypatch):
    preview=client.post('/api/risk',json={'scenario':'A','week':11,'duration':2,'closure_location':'SEC:BET:H01_H02:EB'}).json()
    post(client,'Apply this plan.',forecast_id=preview['id'])
    past=[r for r in main.baseline('A')['accesses'] if r['week']<11]
    route(monkeypatch,action='add_people',crew=[dict(name='Jamie Tan',role='Technician',skills=['track'])])
    result=post(client,'Add Jamie Tan as a technician qualified in track work.')
    assert result['receipt']
    plan=main.baseline('A')
    assert plan['options']['closure_location']=='SEC:BET:H01_H02:EB'
    assert [r for r in plan['accesses'] if r['week']<11]==past
    assert plan['audit']['passed']

def test_forecast_survives_explanation_failure(client,monkeypatch):
    responses=route(monkeypatch,action='answer')
    def broken(**kw): raise RuntimeError('private-provider-error')
    responses.create=broken
    result=post(client,'Simulate SEC:BET:H01_H02:EB closed in week 11 for 2 weeks.')
    assert result['forecast'] and result['ai_error']
    assert 'private-provider-error' not in json.dumps(result)
    assert not main.baseline('A')['options']

def test_changed_workspace_rejects_routed_write(client,monkeypatch):
    responses=route(monkeypatch,action='add_people',crew=[dict(name='Jamie Tan',role='Engineer',skills=['track'])])
    original=responses.parse
    def change_while_routing(**kw):
        with Session.begin() as session:
            p=session.get(Person,people()[0]['id']); p.max_shifts=2
        return original(**kw)
    responses.parse=change_while_routing
    result=post(client,'Add Jamie Tan as an engineer with track skills.')
    assert result['action_error'] and len(people())==24
