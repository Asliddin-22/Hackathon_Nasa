import hashlib
import json
import uuid
from sqlalchemy import select
from ..models.records import Assessment, Alert, AuditEvent
from ..risk_modules.trends import MODULES, evaluate
from .ai_assistant import explain
from .safety import safety_actions

PERIODIC = {'bone': 'DXA scans and clinical bone-health assessments', 'kidney': 'Urinalysis and clinical kidney-health assessments', 'vision': 'OCT scans and vision examinations'}

def run_assessments(db, user_id, actor, origin='simulated', use_llm=False):
    output = []
    for module in [*MODULES, *PERIODIC]:
        if module in MODULES:
            finding = evaluate(db, user_id, module, origin)
        else:
            finding = {'module': module, 'status': 'assessment_required',
                       'observation': f'{PERIODIC[module]} are required. Wearable telemetry cannot assess this condition.',
                       'statistics': {'origin': origin, 'data_status': 'assessment_required'},
                       'certainty': 'Current clinical status is unknown.', 'doctor_review': False, 'references': ['nasa-body']}
        finding['explanation'] = explain(finding, use_llm)
        finding['actions'] = safety_actions() if finding['doctor_review'] else []
        fingerprint = hashlib.sha256(json.dumps({'user_id': user_id, 'module': module, 'finding': finding}, sort_keys=True).encode()).hexdigest()
        existing = db.scalar(select(Assessment).where(Assessment.fingerprint == fingerprint))
        if existing:
            output.append({**existing.findings, 'assessment_id': existing.id, 'timestamp': existing.timestamp})
            continue
        row = Assessment(id=str(uuid.uuid4()), user_id=user_id, module=module, findings=finding, fingerprint=fingerprint)
        db.add(row)
        db.flush()
        # A persistent episode has one active alert per module; new evidence updates it.
        active = db.scalar(select(Alert).where(Alert.user_id == user_id, Alert.module == module, Alert.status.in_(['open', 'reviewed'])))
        if finding['doctor_review']:
            if active:
                active.assessment_id = row.id
                active.evidence = finding
            else:
                db.add(Alert(id=str(uuid.uuid4()), user_id=user_id, assessment_id=row.id, module=module,
                             title=finding['observation'], severity='review', evidence=finding))
        output.append({**finding, 'assessment_id': row.id, 'timestamp': row.timestamp})
    db.add(AuditEvent(actor=actor, action='analysis.completed', detail={'user_id': user_id, 'origin': origin, 'modules': list(MODULES)}))
    db.flush()
    return output
