import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database.db import get_db
from ..models.records import Symptom, Alert, AuditEvent
from ..services.auth import astronaut
from ..services.risk_engine import run_assessments
from ..services.safety import safety_actions
from ..services.records import serialize
from ..services.earth_sync import queue_snapshot

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
    urgent = data.warning_signs or data.severity >= 8
    report = Symptom(id=str(uuid.uuid4()), user_id=user.id, **data.model_dump())
    db.add(report)
    actions = safety_actions(urgent)
    alert = Alert(id=str(uuid.uuid4()), user_id=user.id, module='symptoms',
                  title='Reported warning signs need onboard attention' if urgent else 'Symptom report awaiting medical review',
                  severity='urgent' if urgent else 'review', evidence={'symptom_id': report.id, 'description': data.description,
                  'severity_self_reported': data.severity, 'warning_signs': data.warning_signs, 'origin': data.origin,
                  'actions': actions, 'rule': 'Demo self-reported warning signs or severity >= 8; not validated triage.'})
    db.add(alert)
    db.flush()
    queue_snapshot(db, user.id)
    db.add(AuditEvent(actor=user.id, action='symptom.reported', detail={'id': report.id, 'urgent': urgent}))
    db.commit()
    return {'report': serialize(report), 'alert': serialize(alert), 'actions': actions,
            'explanation': 'Your report has been recorded. Its cause has not been determined. Onboard escalation does not depend on Earth delivery.'}
