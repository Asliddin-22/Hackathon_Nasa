"""Local store-and-forward simulation with a distinct ground snapshot boundary.
No spacecraft network is contacted. Delay is demo wall-clock seconds per leg.
"""
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from ..models.records import Mission, SyncEvent, GroundRecord, Review, Alert, AuditEvent, now
from .crypto import encrypt, decrypt
from ..models.knowledge import GroundAssistantMessage,AssistantMessage
from .records import snapshot


def enqueue(db, user_id, destination, kind, payload, immediate=False):
    mission = db.get(Mission, 'ares-01')
    event = SyncEvent(id=str(uuid.uuid4()), user_id=user_id, destination=destination, kind=kind,
                      payload=encrypt(payload), available_at=(datetime.now(timezone.utc) + timedelta(seconds=0 if immediate else mission.delay_seconds)).isoformat())
    db.add(event)
    db.flush()
    return event


def queue_snapshot(db, user_id, immediate=False, assistant_message_id=None):
    payload=snapshot(db,user_id)
    # A slow/retried older job may finish after it falls outside the recent
    # snapshot window. Always include the turn that triggered this downlink.
    if assistant_message_id and assistant_message_id not in {m['id'] for m in payload['assistant_messages']}:
        message=db.get(AssistantMessage,assistant_message_id)
        if message and message.user_id==user_id:payload['assistant_messages'].append({'id':message.id,**message.response})
    return enqueue(db, user_id, 'earth', 'health_snapshot', payload, immediate)


def deliver(db, actor):
    mission = db.get(Mission, 'ares-01')
    if not mission.online:
        return {'delivered': 0, 'status': 'offline'}
    count = 0
    events = list(db.scalars(select(SyncEvent).where(SyncEvent.status == 'queued', SyncEvent.available_at <= now()).order_by(SyncEvent.created_at, SyncEvent.id)))
    for event in events:
        try:
            # A savepoint keeps any malformed message from partially changing its recipient.
            with db.begin_nested():
                payload = decrypt(event.payload)
                if event.kind == 'health_snapshot':
                    for message in payload.get('assistant_messages',[]):
                        archived=db.get(GroundAssistantMessage,message['id'])
                        if archived is None:
                            db.add(GroundAssistantMessage(message_id=message['id'],user_id=event.user_id,payload=message,captured_at=payload['captured_at'],received_at=now()))
                        elif archived.captured_at<=payload['captured_at']:
                            archived.payload=message;archived.captured_at=payload['captured_at'];archived.received_at=now()
                    existing = db.get(GroundRecord, event.user_id)
                    if not existing:
                        db.add(GroundRecord(user_id=event.user_id, snapshot=payload, captured_at=payload['captured_at'], received_at=now()))
                    elif existing.captured_at <= payload['captured_at']:
                        existing.snapshot, existing.captured_at, existing.received_at = payload, payload['captured_at'], now()
                elif event.kind == 'doctor_review':
                    review = db.get(Review, payload['review_id'])
                    if review and not review.delivered_at:
                        review.delivered_at = now()
                        alert = db.get(Alert, review.alert_id)
                        if alert:
                            alert.status = 'reviewed'
                        db.flush()
                        queue_snapshot(db, review.user_id)
                else:
                    raise ValueError('Unsupported event kind')
                event.status, event.delivered_at = 'delivered', now()
                db.flush()
            count += 1
        except Exception:
            # The original ciphertext is retained for retry and inspection.
            event.retry_count += 1
            event.available_at = (datetime.now(timezone.utc) + timedelta(seconds=min(60, 2 ** min(event.retry_count, 6)))).isoformat()
    if count:
        mission.last_sync = now()
        db.add(AuditEvent(actor=actor, action='sync.delivered', detail={'count': count}))
    db.flush()
    return {'delivered': count, 'status': 'connected'}


def bootstrap(db):
    """First-run synthetic downlink fixture; normal updates obey configured delay."""
    from .risk_engine import run_assessments
    from ..models.records import User
    if db.scalar(select(GroundRecord).limit(1)):
        return
    for user in db.scalars(select(User).where(User.role == 'astronaut')):
        run_assessments(db, user.id, 'demo-initializer')
        queue_snapshot(db, user.id, immediate=True)
    deliver(db, 'demo-initializer')
    db.commit()
