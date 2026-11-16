from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..database.db import Base

def now():
    return datetime.now(timezone.utc).isoformat()

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    role: Mapped[str]
    password_hash: Mapped[str]

class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[str]

class Mission(Base):
    __tablename__ = 'missions'
    id: Mapped[str] = mapped_column(primary_key=True)
    profile: Mapped[str]
    environment: Mapped[str]
    gravity: Mapped[str]
    start_time: Mapped[str]
    online: Mapped[bool] = mapped_column(default=True)
    delay_seconds: Mapped[int] = mapped_column(default=20)
    last_sync: Mapped[str | None] = mapped_column(nullable=True)

class Measurement(Base):
    __tablename__ = 'health_measurements'
    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    metric: Mapped[str] = mapped_column(index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str]
    timestamp: Mapped[str] = mapped_column(index=True)
    received_at: Mapped[str] = mapped_column(default=now)
    source: Mapped[str]
    origin: Mapped[str]
    quality: Mapped[str]

class Baseline(Base):
    __tablename__ = 'health_baselines'
    __table_args__ = (UniqueConstraint('user_id', 'metric', 'origin'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    metric: Mapped[str]
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str]
    period: Mapped[str]
    origin: Mapped[str]

class MedicalTest(Base):
    __tablename__ = 'medical_tests'
    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    test_type: Mapped[str]
    results: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[str]
    origin: Mapped[str]
    file_reference: Mapped[str | None] = mapped_column(nullable=True)

class Symptom(Base):
    __tablename__ = 'symptom_reports'
    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    description: Mapped[str]
    severity: Mapped[int]
    warning_signs: Mapped[bool]
    timestamp: Mapped[str] = mapped_column(default=now)
    origin: Mapped[str]

class Assessment(Base):
    __tablename__ = 'risk_assessments'
    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    module: Mapped[str]
    findings: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[str] = mapped_column(default=now)
    fingerprint: Mapped[str] = mapped_column(unique=True)

class Alert(Base):
    __tablename__ = 'alerts'
    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    assessment_id: Mapped[str | None] = mapped_column(ForeignKey('risk_assessments.id'), nullable=True)
    module: Mapped[str]
    title: Mapped[str]
    severity: Mapped[str]
    status: Mapped[str] = mapped_column(default='open')
    created_at: Mapped[str] = mapped_column(default=now)
    evidence: Mapped[dict] = mapped_column(JSON)

class Review(Base):
    __tablename__ = 'doctor_reviews'
    id: Mapped[str] = mapped_column(primary_key=True)
    alert_id: Mapped[str]
    user_id: Mapped[str]
    doctor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    assessment: Mapped[str]
    feedback: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)
    delivered_at: Mapped[str | None] = mapped_column(nullable=True)
    acknowledged_at: Mapped[str | None] = mapped_column(nullable=True)

class Protocol(Base):
    __tablename__ = 'medical_protocols'
    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    version: Mapped[str]
    approval_status: Mapped[str]
    steps: Mapped[list] = mapped_column(JSON)
    references: Mapped[list] = mapped_column(JSON)

class SyncEvent(Base):
    __tablename__ = 'sync_queue'
    id: Mapped[str] = mapped_column(primary_key=True)
    destination: Mapped[str]
    kind: Mapped[str]
    user_id: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default='queued')
    retry_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[str] = mapped_column(default=now)
    available_at: Mapped[str]
    delivered_at: Mapped[str | None] = mapped_column(nullable=True)

class GroundRecord(Base):
    __tablename__ = 'ground_records'
    user_id: Mapped[str] = mapped_column(primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    captured_at: Mapped[str]
    received_at: Mapped[str]

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str]
    action: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[str] = mapped_column(default=now)
