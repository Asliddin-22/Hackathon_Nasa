"""Short-window wearable monitoring rules.

Team-authored experimental demo settings. They are NOT clinical thresholds, do
not diagnose anything, and only request human review. They run on every origin
(simulated, manual, device) because they use absolute values rather than a
synthetic personal baseline. No AI is involved, so they work fully offline.
"""
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from ..models.records import Measurement, Alert, AuditEvent
from .safety import safety_actions

WATCH_RULES = {
    'watch_resting_hr': {
        'metric': 'resting_hr', 'compare': 'gte', 'limit': 100.0, 'count': 3, 'window_minutes': 30,
        'title': 'G2: resting heart rate stayed elevated',
        'description': 'Three consecutive resting heart-rate readings were at or above 100 bpm within 30 minutes. The cause has not been established.',
    },
    'watch_spo2': {
        'metric': 'spo2', 'compare': 'lt', 'limit': 92.0, 'count': 2, 'window_minutes': 15,
        'title': 'G2: blood oxygen readings were low',
        'description': 'Two consecutive blood-oxygen readings were below 92% within 15 minutes. Wrist readings can be affected by fit and motion. The cause has not been established.',
    },
}
AUTHORITY = 'Team experimental demo setting; not a NASA requirement or validated clinical threshold.'


def _matches(rule, value):
    return value >= rule['limit'] if rule['compare'] == 'gte' else value < rule['limit']


def evaluate_watch_rules(db, user_id, metrics, origins):
    """Evaluate rules touched by the new metrics. Returns alerts created or updated."""
    touched = []
    for module, rule in WATCH_RULES.items():
        if rule['metric'] not in metrics:
            continue
        for origin in origins:
            rows = list(db.scalars(select(Measurement).where(
                Measurement.user_id == user_id, Measurement.metric == rule['metric'],
                Measurement.origin == origin, Measurement.quality == 'valid',
                Measurement.timestamp >= (datetime.now(timezone.utc)-timedelta(minutes=rule['window_minutes'])).isoformat(),
            ).order_by(Measurement.timestamp.desc()).limit(rule['count'])))
            if len(rows) < rule['count']:
                continue
            span = datetime.fromisoformat(rows[0].timestamp) - datetime.fromisoformat(rows[-1].timestamp)
            if span > timedelta(minutes=rule['window_minutes']) or not all(_matches(rule, r.value) for r in rows):
                continue
            evidence = {
                'description': rule['description'], 'rule': {'module': module, 'metric': rule['metric'],
                'comparison': rule['compare'], 'limit': rule['limit'], 'consecutive_readings': rule['count'],
                'window_minutes': rule['window_minutes'], 'authority': AUTHORITY},
                'readings': [{'id': r.id, 'value': r.value, 'unit': r.unit, 'timestamp': r.timestamp,
                              'device_id': r.device_id, 'source': r.source} for r in reversed(rows)],
                'origin': origin, 'actions': safety_actions(),
                'certainty': 'Cause not established. This is an experimental monitoring notification, not a diagnosis.',
            }
            # One active alert per rule; new matching evidence updates it.
            active = db.scalar(select(Alert).where(Alert.user_id == user_id, Alert.module == module,
                                                   Alert.status.in_(['open', 'reviewed']),
                                                   Alert.evidence['origin'].as_string()==origin))
            if active:
                if active.evidence.get('readings', [{}])[-1].get('id') == evidence['readings'][-1]['id']:
                    continue
                active.evidence = evidence
                alert = active
            else:
                alert = Alert(id=str(uuid.uuid4()), user_id=user_id, module=module, title=rule['title'],
                              severity='review', evidence=evidence)
                db.add(alert)
                db.add(AuditEvent(actor='watch-monitor', action='watch_alert.created',
                                  detail={'user_id': user_id, 'module': module, 'origin': origin}))
            db.flush()
            touched.append({'id': alert.id, 'module': module, 'title': alert.title, 'severity': alert.severity, 'origin': origin})
    return touched
