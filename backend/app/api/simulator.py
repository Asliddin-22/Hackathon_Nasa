import random
import uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..config import SEED_DEMO
from ..database.db import get_db
from ..models.records import Measurement
from ..services.auth import astronaut
from ..services.ingestion import Reading, ingest
from ..services.risk_engine import run_assessments
from ..services.earth_sync import queue_snapshot

router = APIRouter(prefix='/api/simulator')

class Tick(BaseModel):
    scenario: Literal['nominal', 'trend'] = 'trend'

@router.post('/tick')
def tick(data: Tick, user=Depends(astronaut), db: Session = Depends(get_db)):
    if not SEED_DEMO:
        raise HTTPException(403, 'Simulator is disabled')
    # Samples are appended, never replacing history. A live tick alone cannot
    # satisfy the longitudinal rule requiring three distinct collection days.
    measures = {'resting_hr': (82 if data.scenario == 'trend' else 65, 'bpm'),
                'hrv': (41 if data.scenario == 'trend' else 52, 'ms'),
                'strength': (36.8 if data.scenario == 'trend' else 42, 'kg'),
                'balance_sway': (2.7 if data.scenario == 'trend' else 2, 'deg')}
    for metric, (value, unit) in measures.items():
        ingest(db, Reading(id=str(uuid.uuid4()), user_id=user.id, metric=metric,
                          value=round(value + random.uniform(-.2, .2), 2), unit=unit,
                          timestamp=datetime.now(timezone.utc), source='Live synthetic simulator', origin='simulated'), user.id)
    results = run_assessments(db, user.id, user.id)
    event = queue_snapshot(db, user.id)
    db.commit()
    return {'inserted': len(measures), 'assessments': results, 'sync_event_id': event.id, 'origin': 'simulated'}
