"""Universal mechanisms, not disease-specific production answer fixtures."""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock
import pytest
from sqlalchemy import select,func
from backend.app.models.records import Protocol,SyncEvent,Alert
from backend.app.models.knowledge import AssistantMessage,AssistantJob,GroundAssistantMessage
from backend.app.services import conversation,meta_model,assistant_jobs,emergency_support
from backend.app.services.earth_sync import queue_snapshot
from backend.app.services.knowledge import ingest_corpus
from backend.tests.test_medical_assistant import plan,generated,mock_model

@pytest.fixture
def corpus(client):
    with client.sessions() as db:ingest_corpus(db);db.commit()

CASES=[
 ('cardiovascular','A new irregular pulse started while resting. What could explain it?',['resting_hr','systolic_bp']),
 ('respiratory','Breathing feels much harder than yesterday and I need immediate assistance.',['resting_hr']),
 ('neurological','My hand coordination changed abruptly and I cannot describe it well.',[]),
 ('musculoskeletal','A limb hurts after an unfamiliar exercise movement. What should I consider?',['strength']),
 ('renal','Urine output changed and there is discomfort. How can we assess the possibilities?',['hydration']),
 ('vision','I see an unfamiliar visual disturbance that started just now.',[]),
 ('minor_illness','I have throat irritation and feel unwell after a busy shift.',[]),
 ('spaceflight','Head movements feel unusual after a gravity transition.',['balance_sway']),
]


def install_reasoning(monkeypatch,metrics,urgent=True):
    routing=plan('personal_assessment',uses_patient_records=True,metrics=metrics,include_history=bool(metrics),include_symptoms=True,include_mission=True,use_conversation_history=True,symptom_scope='current')
    def body(data):
        # Fixtures generate new prose and questions, not IDs from an answer list.
        first='The timing and associated findings can help distinguish a common reversible contributor from a more serious process; the available evidence does not establish which explanation applies.'
        next_step='Activate local assistance and use the trained crew response without waiting for Earth or for answers to these questions.' if urgent else 'Record the timing and associated changes, and seek an assessment if the problem persists or worsens.'
        basis='retrieved_evidence' if urgent else 'general_model_knowledge'
        citation_ids=['medlineplus-first-aid:1'] if urgent else []
        return generated(first,
          blocks=[{'id':'explanation','text':first,'basis':'clinical_inference','citation_ids':[],'fact_ids':['user_report']},
                  {'id':'next_step','text':next_step,'basis':basis,'citation_ids':citation_ids,'fact_ids':[]}],
          short_answer={'explanation_id':'explanation','recommendation_id':'next_step'},
          possible_explanations=[{'title':'A contextual, potentially reversible contributor','text':'Workload, environment, or an intercurrent illness could contribute depending on the history.','basis':'clinical_inference','citation_ids':[],'fact_ids':['user_report']},
                                 {'title':'A more serious underlying process','text':'An urgent process cannot be excluded from symptoms and available measurements alone.','basis':'clinical_inference','citation_ids':[],'fact_ids':['user_report']}],
          follow_up_questions=['What changed just before this began, and what has changed since?','Is another trained crewmember able to help while you provide this information?'],
          recommendations=[{'text':next_step,'basis':basis,'citation_ids':citation_ids,'fact_ids':[]}],
          needs_medical_review=True,needs_urgent_attention=urgent)
    return mock_model(monkeypatch,routing,body)


@pytest.mark.parametrize('category,question,metrics',CASES)
def test_any_reported_emergency_keeps_reasoning_context_and_chat(client,corpus,astronaut,monkeypatch,category,question,metrics):
    calls=install_reasoning(monkeypatch,metrics)
    initial=client.post('/api/assistant/messages',headers=astronaut,json={'question':question,'warning_signs':True,'wait_for_completion':False,'medical_personnel_available':False}).json()
    assert initial['safety']['urgent'] and initial['generation_status']=='queued'
    assert initial['safety']['immediate_guidance'] and initial['safety']['do_not_delay_for_questions']
    result=client.get('/api/assistant/messages/'+initial['id'],headers=astronaut).json()
    assert result['generation_status']=='complete' and result['mode']=='muse_wonder_generated'
    assert result['safety']['urgent']  # Reasoning can never clear the overlay.
    assert result['detailed']['possible_explanations'] and result['detailed']['follow_up_questions']
    assert result['detailed']['emergency_guidance'] and result['detailed']['recommendations']
    assert {o['metric'] for o in result['detailed']['patient_observations']}<=set(metrics)
    assert result['short_answer']==' '.join(b['text'] for b in result['detailed']['reasoning'] if b['id'] in result['short_answer_block_ids'])
    packet=next(data for name,data,_ in calls if name=='medical_conversation_answer')
    assert packet['local_safety']['urgent'] and packet['reported_support_availability']['medical_personnel_available'] is False
    follow=client.post('/api/assistant/messages',headers=astronaut,json={'question':'The situation has changed, and there is no medical officer nearby. What information is most useful now?',
        'conversation_id':initial['conversation_id'],'parent_id':initial['id'],'wait_for_completion':False}).json()
    continued=client.get('/api/assistant/messages/'+follow['id'],headers=astronaut).json()
    assert continued['generation_status']=='complete' and continued['safety']['urgent']
    assert continued['conversation_id']==initial['conversation_id']
    assert continued['safety']['support']['medical_personnel_available'] is False
    assert any(data.get('context') for name,data,_ in calls if name=='medical_conversation_answer')
    with client.sessions() as db:assert db.scalar(select(func.count()).select_from(AssistantMessage))==2


def test_local_warning_is_persisted_while_generation_is_blocked(client,corpus,astronaut,monkeypatch):
    started=threading.Event();release=threading.Event()
    calls=install_reasoning(monkeypatch,['resting_hr'])
    real=meta_model.request_structured
    def slow(name,*args,**kwargs):
        if name=='medical_context_plan':
            started.set();assert release.wait(5)
        return real(name,*args,**kwargs)
    monkeypatch.setattr(meta_model,'request_structured',slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(client.post,'/api/assistant/messages',headers=astronaut,json={'question':'An unfamiliar critical situation is occurring','warning_signs':True,'wait_for_completion':False})
        try:
            assert started.wait(3)
            with client.sessions() as db:
                message=db.scalar(select(AssistantMessage))
                assert message.response['safety']['urgent']
                assert message.response['safety']['immediate_guidance']
                assert db.scalar(select(Alert).where(Alert.module=='assistant')).severity=='urgent'
                assert db.scalar(select(SyncEvent).where(SyncEvent.status=='queued'))
        finally:release.set()
        assert future.result(timeout=5).status_code==201


def test_provider_failure_retains_guidance_and_allows_followup(client,corpus,astronaut,monkeypatch):
    monkeypatch.setattr(conversation,'llm_enabled',lambda:True)
    def failure(*args,**kwargs):raise TimeoutError('mock-only failure')
    monkeypatch.setattr(meta_model,'request_structured',failure)
    first=client.post('/api/assistant/messages',headers=astronaut,json={'question':'I need immediate assistance','severity':9,'wait_for_completion':False}).json()
    failed=client.get('/api/assistant/messages/'+first['id'],headers=astronaut).json()
    assert failed['generation_status']=='failed'
    assert failed['safety']['urgent'] and failed['detailed']['emergency_guidance']
    assert failed['safety']['protocol_status']=='no_mission_approved_clinical_procedure_installed'
    second=client.post('/api/assistant/messages',headers=astronaut,json={'question':'Can I continue providing updates?', 'conversation_id':first['conversation_id'],'parent_id':first['id'],'wait_for_completion':False})
    assert second.status_code==201
    assert second.json()['safety']['urgent']
    assert len(client.get('/api/assistant/messages',headers=astronaut).json())==2


def test_protocol_approval_is_not_invented(client,astronaut,monkeypatch):
    with client.sessions() as db:
        assert emergency_support.approved_procedures(db)==[]
        # Only a test fixture simulates deployment by an authorized operator.
        db.add(Protocol(id='test-authorized',title='Operator-installed test checklist',version='test-1',approval_status='mission_approved',steps=['Use the authorized test workflow.'],references=['test-reference']))
        db.commit()
        assert [p['id'] for p in emergency_support.approved_procedures(db)]==['test-authorized']


def test_restart_marks_work_interrupted_without_losing_safety_and_retry_works(client,corpus,astronaut,monkeypatch):
    saved_runner=assistant_jobs.finish_message
    monkeypatch.setattr('backend.app.api.assistant.finish_message',lambda *args:None)
    first=client.post('/api/assistant/messages',headers=astronaut,json={'question':'An urgent update','warning_signs':True,'wait_for_completion':False}).json()
    with client.sessions() as db:
        assert assistant_jobs.interrupt_pending(db)==1;db.commit()
    current=client.get('/api/assistant/messages/'+first['id'],headers=astronaut).json()
    assert current['generation_status']=='interrupted' and current['safety']['urgent']
    install_reasoning(monkeypatch,[])
    monkeypatch.setattr('backend.app.api.assistant.finish_message',saved_runner)
    assert client.post('/api/assistant/messages/'+first['id']+'/retry',headers=astronaut).status_code==202
    assert client.get('/api/assistant/messages/'+first['id'],headers=astronaut).json()['generation_status']=='complete'


def make_due(client):
    with client.sessions() as db:
        for e in db.scalars(select(SyncEvent).where(SyncEvent.status=='queued')):e.available_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        db.commit()


def test_every_turn_and_relevant_history_obey_doctor_delivery_policy(client,corpus,astronaut,doctor,monkeypatch):
    client.patch('/api/mission/context',headers=astronaut,json={'online':False,'delay_seconds':30})
    install_reasoning(monkeypatch,['resting_hr'])
    first=client.post('/api/assistant/messages',headers=astronaut,json={'question':'A new emergency report','warning_signs':True,'wait_for_completion':False}).json()
    follow=client.post('/api/assistant/messages',headers=astronaut,json={'question':'A changing symptom update','conversation_id':first['conversation_id'],'parent_id':first['id'],'wait_for_completion':False}).json()
    assert client.get('/api/doctors/conversations/astro-01',headers=doctor).json()==[]
    assert client.post('/api/sync',headers=astronaut).json()['status']=='offline'
    client.patch('/api/mission/context',headers=astronaut,json={'online':True})
    assert client.post('/api/sync',headers=astronaut).json()['delivered']==0  # Delay still applies.
    make_due(client);client.post('/api/sync',headers=astronaut)
    delivered=client.get('/api/doctors/conversations/astro-01',headers=doctor).json()
    assert {r['message']['id'] for r in delivered}=={first['id'],follow['id']}
    assert all(r['message']['generation_status']=='complete' for r in delivered)
    assert any(r['message']['detailed']['patient_observations'] for r in delivered)
    assert client.get('/api/doctors/conversations/astro-01',headers=astronaut).status_code==403
    assert client.get('/api/assistant/messages/'+first['id'],headers=doctor).status_code==403


def test_ground_archive_retains_conversations_beyond_snapshot_window(client,astronaut,doctor):
    with client.sessions() as db:
        for i in range(23):
            id=str(uuid.uuid4());response=conversation.base_response(f'Historical fixture {i}','simulated','general_education','generation_unavailable')
            db.add(AssistantMessage(id=id,user_id='astro-01',question=f'Historical fixture {i}',request_hash=id,response=response,created_at=(datetime.now(timezone.utc)+timedelta(microseconds=i)).isoformat()))
            db.flush();queue_snapshot(db,'astro-01')
        db.commit()
    make_due(client);client.post('/api/sync',headers=astronaut)
    assert len(client.get('/api/doctors/conversations/astro-01',headers=doctor).json())==23


@pytest.mark.parametrize('category,question,metrics',CASES)
def test_unfamiliar_personal_presentations_use_same_generation_path(client,corpus,astronaut,monkeypatch,category,question,metrics):
    calls=install_reasoning(monkeypatch,metrics,urgent=False)
    result=client.post('/api/assistant/messages',headers=astronaut,json={'question':question}).json()
    assert result['mode']=='muse_wonder_generated' and not result['safety']['urgent']
    assert result['detailed']['possible_explanations'] and result['detailed']['recommendations']
    assert result['detailed']['follow_up_questions']
    assert {o['metric'] for o in result['detailed']['patient_observations']}<=set(metrics)
    assert [name for name,_,_ in calls]==['medical_context_plan','medical_conversation_answer','medical_answer_audit']


@pytest.mark.parametrize('failure',['unknown_citation','rejected_audit'])
def test_invalid_emergency_generation_cannot_remove_independent_guidance(client,corpus,astronaut,monkeypatch,failure):
    install_reasoning(monkeypatch,[])
    respond=meta_model.request_structured
    def invalid(name,*args,**kwargs):
        output=respond(name,*args,**kwargs)
        if name=='medical_conversation_answer':
            if failure=='unknown_citation':output['blocks'][0]['citation_ids']=['forged-reference']
        if name=='medical_answer_audit' and failure=='rejected_audit':return {'acceptable':False,'issues':['unapproved_treatment']}
        return output
    monkeypatch.setattr(meta_model,'request_structured',invalid)
    first=client.post('/api/assistant/messages',headers=astronaut,json={'question':'An unanticipated emergency report','warning_signs':True}).json()
    final=client.get('/api/assistant/messages/'+first['id'],headers=astronaut).json()
    assert final['generation_status']=='failed' and final['safety']['urgent']
    assert final['detailed']['emergency_guidance'] and 'Conversational generation is unavailable' in final['short_answer']
    assert not final['detailed']['reasoning']


def test_message_status_and_retry_enforce_ownership(client,astronaut):
    first=client.post('/api/assistant/messages',headers=astronaut,json={'question':'A private educational question'}).json()
    other=client.post('/api/auth/login',json={'username':'astronaut2','password':'demo-orbit-2026'}).json()
    headers={'Authorization':'Bearer '+other['token']}
    for method,suffix in [('get',''),('post','/retry')]:
        endpoint='/api/assistant/messages/'+first['id']+suffix
        assert getattr(client,method)(endpoint,headers=headers).status_code==404
        assert getattr(client,method)(endpoint).status_code==401


def test_model_promoted_emergency_publishes_before_enriched_generation(client,corpus,astronaut,monkeypatch):
    calls=mock_model(monkeypatch,plan('personal_assessment',symptom_scope='current'),generated(needs_urgent_attention=True))
    response=client.post('/api/assistant/messages',headers=astronaut,json={'question':'A pattern I cannot characterize has just developed.'}).json()
    packets=[data for name,data,_ in calls if name=='medical_conversation_answer']
    assert len(packets)==2 and not packets[0]['local_safety']['urgent']
    assert packets[1]['local_safety']['urgent']
    assert any(r['chunk_id'].startswith('medlineplus-first-aid:') for r in packets[1]['references'])
    assert any(f['kind']=='mission_context' for f in packets[1]['patient_facts'].values())
    assert response['safety']['urgent'] and response['mode']=='muse_wonder_generated'


def test_late_older_turn_update_is_downlinked_outside_recent_window(client,astronaut,doctor):
    with client.sessions() as db:
        ids=[]
        for i in range(23):
            id=str(uuid.uuid4());ids.append(id)
            response=conversation.base_response(f'Queued fixture {i}','simulated','general_education','pending_generation')
            db.add(AssistantMessage(id=id,user_id='astro-01',question=f'Queued fixture {i}',request_hash=id,response=response,created_at=(datetime.now(timezone.utc)+timedelta(microseconds=i)).isoformat()))
            db.flush();queue_snapshot(db,'astro-01',assistant_message_id=id)
        first=db.get(AssistantMessage,ids[0]);first.response={**first.response,'generation_status':'complete','short_answer':'An older generated response finished after newer turns.'}
        db.flush();queue_snapshot(db,'astro-01',assistant_message_id=ids[0]);db.commit()
    make_due(client);client.post('/api/sync',headers=astronaut)
    archive=client.get('/api/doctors/conversations/astro-01',headers=doctor).json()
    assert len(archive)==23
    assert archive[-1]['message']['id']==ids[0]
    assert next(r['message'] for r in archive if r['message']['id']==ids[0])['generation_status']=='complete'


def test_sync_has_one_real_outer_transaction_including_savepoints(client,astronaut):
    from backend.app.database.db import begin_write
    from backend.app.services.earth_sync import deliver
    with client.sessions() as db:
        event=queue_snapshot(db,'astro-01',immediate=True);event_id=event.id;db.commit()
    with client.sessions() as db:
        begin_write(db)
        assert deliver(db,'test-rollback')['delivered']==1
        db.rollback()  # No savepoint RELEASE may commit recipient/event changes.
    with client.sessions() as db:
        assert db.get(SyncEvent,event_id).status=='queued'
