from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from ..database.db import get_db,begin_write
from ..models.research import ResearchReplay
from ..models.records import AuditEvent
from ..services.auth import astronaut
from ..services import research_replay

router=APIRouter(prefix='/api/research-replay',tags=['Real Research Data Replay'])

class Cursor(BaseModel):
    expected_cursor:int=Field(ge=0,le=481)

class Advance(Cursor):
    count:int=Field(default=1,ge=1,le=481)

def source_status(db,user_id):
    try:return research_replay.status(db,user_id)
    except (OSError,ValueError,KeyError):raise HTTPException(503,'Research source unavailable or failed integrity verification; synthetic monitoring remains available')

@router.get('')
def status(user=Depends(astronaut),db:Session=Depends(get_db)):
    return source_status(db,user.id)

@router.post('/advance')
def advance(data:Advance,user=Depends(astronaut),db:Session=Depends(get_db)):
    begin_write(db)
    replay=db.get(ResearchReplay,user.id)
    if data.expected_cursor!=(replay.cursor if replay else 0):raise HTTPException(409,'Replay advanced elsewhere; refresh before continuing')
    try:inserted=research_replay.advance(db,user.id,data.count)
    except (OSError,ValueError,KeyError):
        db.rollback()
        raise HTTPException(503,'Research import failed; no partial batch was committed')
    result=source_status(db,user.id)
    db.commit()
    return {**result,'inserted':inserted}

@router.post('/restart')
def restart(data:Cursor,user=Depends(astronaut),db:Session=Depends(get_db)):
    begin_write(db)
    replay=db.get(ResearchReplay,user.id)
    if data.expected_cursor!=(replay.cursor if replay else 0):raise HTTPException(409,'Replay advanced elsewhere; refresh before continuing')
    if replay:
        replay.cursor=0
        db.add(AuditEvent(actor=user.id,action='research.playback_restarted',detail={'dataset':'bidmc-01'}))
        db.flush()
    result=source_status(db,user.id)
    db.commit()
    return result

@router.get('/source.csv')
def source(user=Depends(astronaut)):
    try:manifest,_=research_replay.load_source()
    except (OSError,ValueError,KeyError):raise HTTPException(503,'Research source unavailable or failed integrity verification')
    return FileResponse(research_replay.DATA/manifest['file'],media_type='text/csv',filename=manifest['file'])
