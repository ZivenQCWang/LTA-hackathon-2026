"""Optional live-model integration check against a disposable database, never the demo workspace."""
import json,os,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory(prefix='pliz-live-check-') as directory:
    os.environ['DATABASE_URL']='sqlite:///'+(Path(directory)/'test.db').as_posix()
    from fastapi.testclient import TestClient
    from backend import main
    from backend.database import engine,people
    assert os.getenv('OPENAI_API_KEY'),'A configured API key is required for this optional check.'
    outcomes=[]
    try:
        with TestClient(main.app) as client:
            def ask(message,kind=None,**extra):
                response=client.post('/api/copilot',json={'message':message,**extra})
                response.raise_for_status(); result=response.json()
                summary=dict(message=message,reply=result['response'],action=result.get('receipt',{}).get('kind'),clarification=result.get('clarification',False),error=result.get('action_error',False),ai_error=result.get('ai_error'))
                outcomes.append(summary); print(json.dumps(summary),flush=True)
                if kind: assert summary['action']==kind,summary
                return result
            ask('Add Lena Demo as a Technician with track and construction skills, maximum 2 shifts per week.','add_people')
            ask('Mark Lena Demo on leave in weeks 11-12 and update the schedule.','update_person')
            ask('Add a job under C001 at the Beta H02 eastbound platform, starting week 20, requiring 1 work unit, priority 2.','add_activity')
            assert len(people())==25 and len(main.instance()['activities'])==55
            preview=ask('Simulate SEC:BET:H01_H02:EB closed in week 11 for 2 weeks.')
            assert preview['forecast']
            ask('Apply this plan.','apply_forecast',forecast_id=preview['forecast']['id'])
            ask('Rebuild the plan.','rebuild_plan')
            state=client.get('/api/state').json()
            assert state['plan']['audit']['passed'] and not state['plan']['options']
        root=Path(__file__).resolve().parents[1]/'artifacts'/'assistant-actions'
        root.mkdir(parents=True,exist_ok=True)
        (root/'live-verification.json').write_text(json.dumps(outcomes,indent=2),encoding='utf-8')
        print('Live assistant actions passed in an isolated database.',flush=True)
    finally: engine.dispose()
