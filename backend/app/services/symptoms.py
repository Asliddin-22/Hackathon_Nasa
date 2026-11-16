"""Symptom recording shared by the medical assistant page, the G2 watch, and the
simulator's reported-symptom scenario. Severity is a self-report; no keyword
matching or diagnosis is used."""
import uuid
from ..models.records import Symptom, Alert, AuditEvent
from .safety import safety_actions
from .earth_sync import queue_snapshot


def record_symptom(db, user_id, description, severity, warning_signs, origin, actor, queue=True):
    urgent = warning_signs or severity >= 8
    report = Symptom(id=str(uuid.uuid4()), user_id=user_id, description=description, severity=severity,
                     warning_signs=warning_signs, origin=origin)
    db.add(report)
    actions = safety_actions(urgent)
    alert = Alert(id=str(uuid.uuid4()), user_id=user_id, module='symptoms',
                  title='Reported warning signs need onboard attention' if urgent else 'Symptom report awaiting medical review',
                  severity='urgent' if urgent else 'review', evidence={'symptom_id': report.id, 'description': description,
                  'severity_self_reported': severity, 'warning_signs': warning_signs, 'origin': origin,
                  'actions': actions, 'rule': 'Demo self-reported warning signs or severity >= 8; not validated triage.'})
    db.add(alert)
    db.flush()
    if queue:
        queue_snapshot(db, user_id)
    db.add(AuditEvent(actor=actor, action='symptom.reported', detail={'id': report.id, 'urgent': urgent}))
    return report, alert, actions
