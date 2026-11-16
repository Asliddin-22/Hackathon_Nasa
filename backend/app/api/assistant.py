import uuid
from fastapi import APIRouter,BackgroundTasks,Depends,HTTPException
from pydantic import BaseModel,Field
from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database.db import get_db,get_session_factory,begin_write
from ..models.knowledge import AssistantMessage,AssistantThread,AssistantTurn,AssistantJob
from ..models.records import AuditEvent,now
from ..services.auth import astronaut
from ..services.knowledge import digest
from ..services.assistant_jobs import initial_response,finish_message,render_message,update_alert
from ..services.earth_sync import queue_snapshot

router=APIRouter(prefix='/api/assistant',tags=['Medical assistant'])
class QuestionRequest(BaseModel):
    id:uuid.UUID=Field(default_factory=uuid.uuid4)
    conversation_id:uuid.UUID|None=None
    parent_id:uuid.UUID|None=None
    question:str=Field(min_length=3,max_length=1500)
    origin:Literal['simulated','manual','device','imported']='simulated'
    severity:int|None=Field(default=None,ge=1,le=10)
    warning_signs:bool=False
    medical_personnel_available:bool|None=None
    wait_for_completion:bool=True


def conversation_history(db,user_id,thread_id,parent_id):
    history=[];cursor=parent_id
    for _ in range(8):
        if not cursor:break
        turn=db.get(AssistantTurn,cursor);message=db.get(AssistantMessage,cursor)
        if not turn or turn.thread_id!=thread_id or not message or message.user_id!=user_id:raise HTTPException(404,'Conversation parent not found')
        job=db.get(AssistantJob,cursor)
        history.append({'reported_support':job.request.get('support',{}) if job else {},'question':message.question,'answer':message.response['short_answer'],'intent':message.response.get('intent','unresolved'),
                        'generation_status':message.response.get('generation_status','complete'),'safety':{'urgent':message.response.get('safety',{}).get('urgent',False)}})
        cursor=turn.parent_message_id
    return list(reversed(history))

@router.post('/messages',status_code=201)
def ask(data:QuestionRequest,background:BackgroundTasks,user=Depends(astronaut),db:Session=Depends(get_db),factory=Depends(get_session_factory)):
    begin_write(db)
    request_hash=digest(data.model_dump(mode='json',exclude={'id','wait_for_completion'}))
    prior=db.get(AssistantMessage,str(data.id))
    if prior:
        if prior.user_id!=user.id or prior.request_hash!=request_hash:raise HTTPException(409,'Message ID conflicts with an existing request')
        return render_message(prior)
    thread_id=str(data.conversation_id) if data.conversation_id else str(uuid.uuid4())
    thread=None
    if data.conversation_id:
        thread=db.get(AssistantThread,thread_id)
        if not thread or thread.user_id!=user.id:raise HTTPException(404,'Conversation not found')
    elif data.parent_id:raise HTTPException(422,'A conversation ID is required with a parent ID')
    parent_id=str(data.parent_id) if data.parent_id else None
    history=conversation_history(db,user.id,thread_id,parent_id) if parent_id else []
    parent=db.get(AssistantMessage,parent_id) if parent_id else None
    result=initial_response(db,data,thread_id,parent_id,parent.response if parent else None)
    if thread is None:db.add(AssistantThread(id=thread_id,user_id=user.id,created_at=now()));db.flush()
    message=AssistantMessage(id=str(data.id),user_id=user.id,question=data.question,request_hash=request_hash,response=result,created_at=now())
    db.add(message);db.flush()
    db.add(AssistantTurn(message_id=message.id,thread_id=thread_id,parent_message_id=parent_id))
    db.add(AssistantJob(message_id=message.id,user_id=user.id,status='queued',updated_at=now(),request={
        'question':data.question,'origin':data.origin,'severity':data.severity,'warning_signs':data.warning_signs,'history':history,
        'support':result['safety'].get('support',{'medical_personnel_available':data.medical_personnel_available})}))
    update_alert(db,message,result['safety']['urgent'],result.get('needs_medical_review',False))
    db.add(AuditEvent(actor=user.id,action='assistant.question_recorded',detail={'id':message.id,'origin':data.origin,'urgent':result['safety']['urgent']}))
    db.flush();queue_snapshot(db,user.id,assistant_message_id=message.id);db.commit()
    initial=render_message(message)
    # Every client may request immediate delivery; recognized explicit/carrying
    # emergencies always deliver local guidance before any remote work.
    if not data.wait_for_completion or result['safety']['urgent']:
        background.add_task(finish_message,message.id,factory)
        return initial
    finish_message(message.id,factory)
    db.expire_all()
    return render_message(db.get(AssistantMessage,message.id))

@router.get('/messages')
def history(user=Depends(astronaut),db:Session=Depends(get_db)):
    return [render_message(r) for r in db.scalars(select(AssistantMessage).where(AssistantMessage.user_id==user.id).order_by(AssistantMessage.created_at.desc()).limit(20))]

@router.get('/messages/{message_id}')
def status(message_id:str,user=Depends(astronaut),db:Session=Depends(get_db)):
    message=db.get(AssistantMessage,message_id)
    if not message or message.user_id!=user.id:raise HTTPException(404,'Message not found')
    return render_message(message)

@router.post('/messages/{message_id}/retry',status_code=202)
def retry(message_id:str,background:BackgroundTasks,user=Depends(astronaut),db:Session=Depends(get_db),factory=Depends(get_session_factory)):
    begin_write(db)
    message=db.get(AssistantMessage,message_id)
    if not message or message.user_id!=user.id:raise HTTPException(404,'Message not found')
    job=db.get(AssistantJob,message_id)
    if not job:raise HTTPException(409,'This historical message has no resumable generation job')
    if job.status in ('failed','interrupted'):
        job.status='queued';job.updated_at=now()
        message.response={**message.response,'generation_status':'queued'}
        db.commit();background.add_task(finish_message,message_id,factory)
    return render_message(message)
