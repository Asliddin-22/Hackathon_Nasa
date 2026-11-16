"""Common sensor-ingestion interface.

Every source (live simulator, manual entry, and future verified device adapters)
goes through ``Reading`` validation and ``ingest_and_monitor``. Bounds are
engineering validation limits, not medical alarm limits.
"""
import math
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from ..models.records import Measurement, AuditEvent, Baseline

# metric: (unit, lower bound, upper bound)
METRICS = {
    'resting_hr': ('bpm', 20, 250), 'hrv': ('ms', 1, 500),
    'systolic_bp': ('mmHg', 40, 280), 'diastolic_bp': ('mmHg', 20, 180),
    'strength': ('kg', 0, 400), 'balance_sway': ('deg', 0, 180),
    'exercise_minutes': ('min', 0, 1440), 'hydration': ('mL', 0, 15000),
    # Wrist-wearable metrics added for the G2 watch pipeline.
    'heart_rate': ('bpm', 20, 250), 'spo2': ('%', 50, 100),
    'sleep_hours': ('h', 0, 24), 'steps': ('count', 0, 100000),
}

# Provenance values. "device" means a verified device source and is reserved for
# registered device adapters; the browser cannot claim it (see api/core.py).
ORIGINS = ('simulated', 'manual', 'imported', 'device')
PROVENANCE_LABELS = {'simulated': 'Simulated', 'manual': 'Manually entered',
                     'imported': 'Imported record', 'device': 'Verified device source'}


class Reading(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    # Derived from the authenticated identity at the API boundary. A supplied
    # value must match it; it is accepted only for backward compatibility.
    user_id: str | None = None
    metric: str
    value: float
    unit: str
    timestamp: datetime
    source: str = Field(min_length=1, max_length=120)
    device_id: str | None = Field(default=None, max_length=120)
    origin: Literal['simulated', 'manual', 'imported', 'device']
    quality: Literal['valid', 'suspect', 'invalid'] = 'valid'

    @field_validator('timestamp')
    @classmethod
    def timestamp_valid(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Timezone is required')
        value = value.astimezone(timezone.utc)
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError('Collection time cannot be in the future')
        return value

    @model_validator(mode='after')
    def metric_valid(self):
        if self.metric not in METRICS:
            raise ValueError('Unsupported metric')
        unit, lower, upper = METRICS[self.metric]
        if self.unit != unit:
            raise ValueError(f'Expected unit {unit}')
        if not math.isfinite(self.value) or not lower <= self.value <= upper:
            raise ValueError('Reading is outside accepted ingestion bounds')
        return self


def ingest(db, data: Reading, actor):
    if not data.user_id:
        raise HTTPException(422, 'Astronaut identity is required')
    values = data.model_dump()
    values['timestamp'] = data.timestamp.isoformat()
    existing = db.get(Measurement, data.id)
    if existing:
        # Same ID and same content is an idempotent retry; anything else conflicts.
        if any(getattr(existing, key) != value for key, value in values.items()):
            raise HTTPException(409, 'Reading ID already exists with different data')
        return existing, False
    row = Measurement(**values)
    db.add(row)
    db.add(AuditEvent(actor=actor, action='measurement.ingest',
                      detail={'id': data.id, 'origin': data.origin, 'metric': data.metric, 'device_id': data.device_id}))
    db.flush()
    return row, True


def ingest_batch_and_monitor(db, readings, user_id, actor, queue=True):
    """Store readings, then run every relevant monitoring workflow once.

    - Short-window watch rules run for every origin (including manual entry).
    - Longitudinal baseline rules run for each origin that has matching personal
      baselines; manual/device data are never compared with synthetic baselines.
    - A new Earth snapshot is queued so ground receives the update after delay.
    """
    from .risk_engine import run_assessments
    from .watch_rules import evaluate_watch_rules
    from .earth_sync import queue_snapshot
    stored, created = [], []
    for reading in readings:
        reading.user_id = user_id
        row, is_new = ingest(db, reading, actor)
        stored.append(row)
        if is_new:
            created.append(row)
    result = {'stored': stored, 'created': created, 'assessments': [], 'watch_alerts': [],
              'longitudinal_skipped': [], 'sync_event_id': None}
    if not created:
        return result
    origins = sorted({row.origin for row in created})
    for origin in origins:
        has_baseline = db.scalar(select(Baseline.id).where(Baseline.user_id == user_id, Baseline.origin == origin).limit(1))
        if has_baseline:
            result['assessments'].extend(run_assessments(db, user_id, actor, origin))
        else:
            result['longitudinal_skipped'].append(origin)
    result['watch_alerts'] = evaluate_watch_rules(db, user_id, {row.metric for row in created}, origins)
    if queue:
        result['sync_event_id'] = queue_snapshot(db, user_id).id
    return result
