import math
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from ..models.records import Measurement, AuditEvent

METRICS = {
    'resting_hr': ('bpm', 20, 250), 'hrv': ('ms', 1, 500),
    'systolic_bp': ('mmHg', 40, 280), 'diastolic_bp': ('mmHg', 20, 180),
    'strength': ('kg', 0, 400), 'balance_sway': ('deg', 0, 180),
    'exercise_minutes': ('min', 0, 1440), 'hydration': ('mL', 0, 15000),
}

class Reading(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    user_id: str
    metric: str
    value: float
    unit: str
    timestamp: datetime
    source: str = Field(min_length=1, max_length=120)
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
    values = data.model_dump()
    values['timestamp'] = data.timestamp.isoformat()
    existing = db.get(Measurement, data.id)
    if existing:
        if any(getattr(existing, key) != value for key, value in values.items()):
            raise HTTPException(409, 'Reading ID already exists with different data')
        return existing, False
    row = Measurement(**values)
    db.add(row)
    db.add(AuditEvent(actor=actor, action='measurement.ingest', detail={'id': data.id, 'origin': data.origin}))
    db.flush()
    return row, True
