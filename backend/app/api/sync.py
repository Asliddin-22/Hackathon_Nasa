from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..database.db import get_db, begin_write
from ..models.records import Mission, SyncEvent, AuditEvent
from ..services.auth import current_user, astronaut
from ..services.earth_sync import deliver, queue_snapshot
from ..services.records import serialize

router = APIRouter(prefix='/api')
PROFILES = {'station': ('Space station', 'Microgravity'), 'moon': ('Lunar surface', '0.16 g'),
            'mars_transit': ('Mars transit', 'Microgravity'), 'mars_surface': ('Mars surface', '0.38 g')}

class MissionUpdate(BaseModel):
    profile: Literal['station', 'moon', 'mars_transit', 'mars_surface'] | None = None
    online: bool | None = None
    delay_seconds: int | None = Field(default=None, ge=0, le=1200)

@router.patch('/mission/context')
def change_context(data: MissionUpdate, user=Depends(astronaut), db: Session = Depends(get_db)):
    begin_write(db)
    mission = db.get(Mission, 'ares-01')
    if data.profile:
        mission.profile = data.profile
        mission.environment, mission.gravity = PROFILES[data.profile]
    if data.online is not None:
        mission.online = data.online
    if data.delay_seconds is not None:
        mission.delay_seconds = data.delay_seconds
    db.add(AuditEvent(actor=user.id, action='mission.updated', detail=data.model_dump(exclude_none=True)))
    db.commit()
    return serialize(mission)

@router.get('/sync')
def status(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(SyncEvent).order_by(SyncEvent.created_at.desc()).limit(100)
    if user.role == 'astronaut':
        query = select(SyncEvent).where(SyncEvent.user_id == user.id).order_by(SyncEvent.created_at.desc()).limit(100)
    events = []
    for row in db.scalars(query):
        event = serialize(row)
        del event['payload']
        events.append(event)
    count_query = select(func.count()).select_from(SyncEvent).where(SyncEvent.status == 'queued')
    if user.role == 'astronaut':
        count_query = count_query.where(SyncEvent.user_id == user.id)
    return {'events': events, 'queued': db.scalar(count_query),
            'transport': 'Encrypted local queue simulation; no external Earth endpoint.'}

@router.post('/sync')
def sync(user=Depends(current_user), db: Session = Depends(get_db)):
    begin_write(db)
    result = deliver(db, user.id)
    db.commit()
    return result

@router.post('/sync/queue')
def queue(user=Depends(astronaut), db: Session = Depends(get_db)):
    begin_write(db)
    event = queue_snapshot(db, user.id)
    db.commit()
    return {'event_id': event.id, 'available_at': event.available_at, 'status': event.status}
