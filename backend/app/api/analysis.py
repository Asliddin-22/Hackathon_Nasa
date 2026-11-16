import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database.db import get_db, begin_write
from ..models.records import Symptom, Alert, AuditEvent
from ..services.auth import astronaut
from ..services.risk_engine import run_assessments
from ..services.safety import safety_actions
from ..services.records import serialize
from ..services.earth_sync import queue_snapshot
from ..services.symptoms import record_symptom

router = APIRouter(prefix='/api')

class AnalysisRequest(BaseModel):
    origin: Literal['simulated', 'manual', 'imported', 'device'] = 'simulated'
    use_llm: bool = False

class SymptomRequest(BaseModel):
    description: str = Field(min_length=3, max_length=2000)
    severity: int = Field(ge=1, le=10)
    warning_signs: bool = False
    origin: Literal['simulated', 'manual'] = 'simulated'

@router.post('/assessments')
def assess(data: AnalysisRequest, user=Depends(astronaut), db: Session = Depends(get_db)):
    begin_write(db)
    results = run_assessments(db, user.id, user.id, data.origin, data.use_llm)
    queue_snapshot(db, user.id)
    db.commit()
    return results

@router.get('/alerts')
def alerts(user=Depends(astronaut), db: Session = Depends(get_db)):
    return [serialize(r) for r in db.scalars(select(Alert).where(Alert.user_id == user.id).order_by(Alert.created_at.desc()))]

@router.post('/symptoms', status_code=201)
def symptoms(data: SymptomRequest, user=Depends(astronaut), db: Session = Depends(get_db)):
    # Severity is a self-report, not an inferred diagnosis. Keyword matching is
    # deliberately not used as a substitute for a clinical triage instrument.
    begin_write(db)
    report, alert, actions = record_symptom(db, user.id, data.description, data.severity, data.warning_signs, data.origin, user.id)
    db.commit()
    return {'report': serialize(report), 'alert': serialize(alert), 'actions': actions,
            'explanation': 'Your report has been recorded. Its cause has not been determined. Onboard escalation does not depend on Earth delivery.'}
