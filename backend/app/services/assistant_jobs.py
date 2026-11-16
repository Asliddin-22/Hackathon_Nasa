"""Persist first; enrich later. Safety and generation have separate lifecycles."""
from copy import deepcopy
from sqlalchemy import select,update
from ..database.db import begin_write
from ..models.knowledge import AssistantMessage,AssistantJob
from ..models.records import Alert,AuditEvent,now
from .conversation import answer,base_response,unavailable_response
from . import emergency_support
from .earth_sync import queue_snapshot


def render_message(row):
    return {'id':row.id,**row.response}


def update_alert(db,message,urgent,review):
    # One alert per message, with monotonic urgent severity.
    alerts=list(db.scalars(select(Alert).where(Alert.user_id==message.user_id,Alert.module=='assistant')))
    alert=next((a for a in alerts if a.evidence.get('assistant_message_id')==message.id),None)
    if not review and not urgent:return
    if alert is None:
        alert=Alert(id=message.id,user_id=message.user_id,module='assistant',title='Medical assistant warning signs' if urgent else 'Medical assistant conversation for review',severity='urgent' if urgent else 'review',evidence={})
        db.add(alert)
    if urgent:alert.severity='urgent';alert.title='Medical assistant warning signs'
    alert.evidence={'description':message.question,'assistant_message_id':message.id,'assistant_response':message.response,'actions':message.response['safety']['actions']}


def initial_response(db,data,thread_id,parent_id,parent_response):
    safety=emergency_support.preflight(db,data.question,data.severity,data.warning_signs,parent_response,
        {'medical_personnel_available':data.medical_personnel_available})
    result=base_response(data.question,data.origin,'unresolved','pending_generation')
    result.update(conversation_id=thread_id,parent_id=parent_id,generation_status='queued')
    result['short_answer']='Your message is saved. The AI explanation is being prepared; you can continue this conversation.'
    result['safety']=safety
    return emergency_support.attach(result,safety)


def finish_message(message_id,factory):
    # Atomic claim prevents duplicate retries from generating in parallel.
    with factory() as db:
        begin_write(db)
        claim=db.execute(update(AssistantJob).where(AssistantJob.message_id==message_id,AssistantJob.status=='queued').values(status='running',updated_at=now()))
        if claim.rowcount!=1:return
        job=db.get(AssistantJob,message_id)
        data=deepcopy(job.request)
        message=db.get(AssistantMessage,message_id)
        message.response={**message.response,'generation_status':'running'}
        db.commit()
        prior=deepcopy(message.response)
        user_id=job.user_id
    def publish_safety(safety):
        with factory() as db:
            begin_write(db)
            message=db.get(AssistantMessage,message_id)
            current=deepcopy(message.response)
            message.response=emergency_support.attach(current,safety)
            message.response={**message.response,'generation_status':'running'}
            update_alert(db,message,True,True)
            db.flush();queue_snapshot(db,user_id,assistant_message_id=message_id);db.commit()
    try:
        with factory() as db:
            result=answer(db,user_id,data['question'],data['origin'],data['severity'],data['warning_signs'],history=data['history'],
                          emergency=prior.get('safety'),on_safety=publish_safety,support=data['support'])
    except Exception:
        # No provider error or private header is written to history/audit.
        result=unavailable_response(data['question'],data['origin'],'worker_failed')
    with factory() as db:
        begin_write(db)
        message=db.get(AssistantMessage,message_id)
        job=db.get(AssistantJob,message_id)
        # Published danger must survive ANY planning/generation/validation failure.
        safety=deepcopy(message.response.get('safety',{}))
        result=emergency_support.attach(result,safety)
        status='complete' if result['mode']=='muse_wonder_generated' else 'failed'
        result.update(created_at=message.created_at,conversation_id=prior['conversation_id'],parent_id=prior.get('parent_id'),generation_status=status,
                      generation_detail=result.get('generation_status'))
        message.response=result
        job.status=status;job.updated_at=now()
        update_alert(db,message,result['safety']['urgent'],result.get('needs_medical_review',False))
        db.add(AuditEvent(actor=user_id,action='assistant.generation_finished',detail={'message_id':message_id,'status':status,'urgent':result['safety']['urgent']}))
        db.flush();queue_snapshot(db,user_id,assistant_message_id=message_id);db.commit()


def interrupt_pending(db):
    """Recover durable chat after restart; never silently lose an urgent turn."""
    count=0
    for job in db.scalars(select(AssistantJob).where(AssistantJob.status.in_(['queued','running']))):
        job.status='interrupted';job.updated_at=now()
        message=db.get(AssistantMessage,job.message_id)
        result=deepcopy(message.response)
        result['generation_status']='interrupted'
        result['generation_detail']='Generation was interrupted; retry explicitly to continue.'
        if not result['safety'].get('urgent'):
            result['short_answer']='Your message is saved, but generation was interrupted. You can retry or continue the conversation.'
        message.response=result
        update_alert(db,message,result['safety'].get('urgent',False),result.get('needs_medical_review',False))
        db.flush();queue_snapshot(db,message.user_id,assistant_message_id=message.id)
        count+=1
    return count
