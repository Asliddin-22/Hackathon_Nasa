from sqlalchemy import select
from ..models.knowledge import AssistantMessage
from ..models.records import Measurement, Baseline, MedicalTest, Assessment, Alert, Review, Symptom, User, now

def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}

def snapshot(db, user_id):
    user = db.get(User, user_id)
    measurements = list(db.scalars(select(Measurement).where(Measurement.user_id == user_id).order_by(Measurement.timestamp)))
    latest = {}
    for row in measurements:
        if row.quality == 'valid':
            latest[row.metric] = serialize(row)
    findings = {}
    for row in db.scalars(select(Assessment).where(Assessment.user_id == user_id).order_by(Assessment.timestamp)):
        findings[row.module] = {**row.findings, 'assessment_id': row.id, 'timestamp': row.timestamp}
    return {'user': {'id': user.id, 'name': user.name, 'role': user.role}, 'captured_at': now(),
            'latest': latest, 'assistant_messages':[{'id':m.id,**m.response} for m in db.scalars(select(AssistantMessage).where(AssistantMessage.user_id==user_id).order_by(AssistantMessage.created_at.desc()).limit(20))], 'baselines': [serialize(r) for r in db.scalars(select(Baseline).where(Baseline.user_id == user_id))],
            'measurements': [serialize(r) for r in measurements],
            'tests': [serialize(r) for r in db.scalars(select(MedicalTest).where(MedicalTest.user_id == user_id))],
            'assessments': list(findings.values()),
            'alerts': [serialize(r) for r in db.scalars(select(Alert).where(Alert.user_id == user_id).order_by(Alert.created_at.desc()))],
            'symptoms': [serialize(r) for r in db.scalars(select(Symptom).where(Symptom.user_id == user_id).order_by(Symptom.timestamp.desc()))],
            'reviews': [serialize(r) for r in db.scalars(select(Review).where(Review.user_id == user_id, Review.delivered_at.is_not(None)).order_by(Review.created_at.desc()))]}
