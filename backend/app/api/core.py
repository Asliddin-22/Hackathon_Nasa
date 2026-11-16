import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from ..config import SEED_DEMO
from ..database.db import get_db, begin_write
from ..models.records import User, AuthSession, Mission, AuditEvent, Protocol
from ..services.auth import current_user, astronaut, own_record, password_matches, issue_token, bearer
from ..services.ingestion import Reading, ingest_batch_and_monitor
from ..services.records import snapshot, serialize
from ..services.earth_sync import queue_snapshot

router = APIRouter(prefix='/api')

class Login(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)

@router.get('/health')
def health():
    return {'status': 'ok', 'mode': 'synthetic-demo' if SEED_DEMO else 'local', 'prediction_models': False}

@router.post('/auth/login')
def login(data: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not password_matches(data.password, user.password_hash):
        raise HTTPException(401, 'Invalid username or password')
    return {'token': issue_token(db, user), 'user': {'id': user.id, 'name': user.name, 'role': user.role}}

@router.post('/auth/logout')
def logout(credentials=Depends(bearer), user=Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(AuthSession).where(AuthSession.token_hash == hashlib.sha256(credentials.credentials.encode()).hexdigest()))
    db.commit()
    return {'status': 'signed_out'}

@router.get('/auth/me')
def me(user=Depends(current_user)):
    return {'id': user.id, 'name': user.name, 'role': user.role}

@router.get('/astronauts/{user_id}/health')
def health_record(user_id: str, user=Depends(astronaut), db: Session = Depends(get_db)):
    own_record(user, user_id)
    return snapshot(db, user_id)

@router.get('/astronauts/{user_id}/history')
def history(user_id: str, user=Depends(astronaut), db: Session = Depends(get_db)):
    own_record(user, user_id)
    return snapshot(db, user_id)['measurements']

@router.post('/measurements', status_code=201)
def measurement(data: Reading, user=Depends(astronaut), db: Session = Depends(get_db)):
    begin_write(db)
    # The astronaut ID always comes from the authenticated session.
    if data.user_id is not None:
        own_record(user, data.user_id)
    if data.origin == 'device':
        # A browser session cannot prove a reading came from a verified device.
        raise HTTPException(403, 'Verified device ingestion requires a registered device adapter, which is not enabled in this milestone.')
    result = ingest_batch_and_monitor(db, [data], user.id, user.id)
    db.commit()
    row = result['stored'][0]
    return {'measurement': serialize(row), 'created': bool(result['created']),
            'monitoring': {'assessments_run': len(result['assessments']), 'watch_alerts': result['watch_alerts'],
                           'longitudinal_skipped_for_origins': result['longitudinal_skipped'],
                           'sync_event_id': result['sync_event_id']}}

@router.get('/mission/context')
def context(user=Depends(current_user), db: Session = Depends(get_db)):
    mission = db.get(Mission, 'ares-01')
    if not mission:
        raise HTTPException(404, 'Mission not configured')
    return {**serialize(mission), 'equipment': ['Heart-rate sensor', 'Resistance trainer', 'Balance test kit', 'Blood-pressure cuff'], 'threshold_policy': 'Experimental detection settings remain constant across mission profiles.'}

@router.get('/protocols')
def protocols(user=Depends(current_user), db: Session = Depends(get_db)):
    return [serialize(r) for r in db.scalars(select(Protocol))]

@router.get('/audit')
def audit(user=Depends(current_user), db: Session = Depends(get_db)):
    return [serialize(r) for r in db.scalars(select(AuditEvent).where(AuditEvent.actor == user.id).order_by(AuditEvent.id.desc()).limit(100))]
