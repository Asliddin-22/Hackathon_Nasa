import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database.db import get_db
from ..models.records import GroundRecord, Review, Alert, AuditEvent, now
from ..services.auth import astronaut, doctor
from ..services.earth_sync import enqueue, queue_snapshot
from ..services.records import serialize

router = APIRouter(prefix='/api')

class ReviewRequest(BaseModel):
    id: uuid.UUID
    user_id: str
    alert_id: str
    assessment: str = Field(min_length=3, max_length=1000)
    feedback: str = Field(min_length=3, max_length=3000)

@router.get('/doctors/crew')
def crew(user=Depends(doctor), db: Session = Depends(get_db)):
    return [{'user_id': row.user_id, 'captured_at': row.captured_at, 'received_at': row.received_at, 'snapshot': row.snapshot}
            for row in db.scalars(select(GroundRecord).order_by(GroundRecord.user_id))]

@router.get('/doctors/reviews')
def reviews(user=Depends(doctor), db: Session = Depends(get_db)):
    result = []
    for row in db.scalars(select(Review).order_by(Review.created_at.desc())):
        ground = db.get(GroundRecord, row.user_id)
        receipt = next((r for r in ground.snapshot['reviews'] if r['id'] == row.id), None) if ground else None
        result.append({**serialize(row), 'acknowledged_at': receipt['acknowledged_at'] if receipt else None})
    return result

@router.post('/doctor-reviews', status_code=201)
def review(data: ReviewRequest, user=Depends(doctor), db: Session = Depends(get_db)):
    existing = db.get(Review, str(data.id))
    if existing:
        if any(getattr(existing, field) != getattr(data, field) for field in ['user_id', 'alert_id', 'assessment', 'feedback']) or existing.doctor_id != user.id:
            raise HTTPException(409, 'Review ID already has different content')
        return serialize(existing)
    ground = db.get(GroundRecord, data.user_id)
    if not ground or data.alert_id not in {a['id'] for a in ground.snapshot['alerts']}:
        raise HTTPException(409, 'Alert has not been delivered to the ground record')
    row = Review(id=str(data.id), doctor_id=user.id, **data.model_dump(exclude={'id'}))
    db.add(row)
    db.flush()
    enqueue(db, data.user_id, 'onboard', 'doctor_review', {'review_id': row.id})
    db.add(AuditEvent(actor=user.id, action='doctor.review_submitted', detail={'review_id': row.id, 'alert_id': row.alert_id}))
    db.commit()
    return serialize(row)

@router.post('/doctor-reviews/{review_id}/acknowledge')
def acknowledge(review_id: str, user=Depends(astronaut), db: Session = Depends(get_db)):
    row = db.get(Review, review_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, 'Review not found')
    if not row.delivered_at:
        raise HTTPException(409, 'Review has not arrived onboard')
    if not row.acknowledged_at:
        row.acknowledged_at = now()
        db.flush()
        queue_snapshot(db, user.id)
        db.add(AuditEvent(actor=user.id, action='doctor.review_acknowledged', detail={'review_id': row.id}))
        db.commit()
    return serialize(row)


@router.get('/doctors/conversations/{user_id}')
def delivered_conversations(user_id:str,offset:int=0,limit:int=100,user=Depends(doctor),db:Session=Depends(get_db)):
    from ..models.knowledge import GroundAssistantMessage
    if offset<0 or not 1<=limit<=200:raise HTTPException(422,'Invalid pagination')
    rows=db.scalars(select(GroundAssistantMessage).where(GroundAssistantMessage.user_id==user_id).order_by(GroundAssistantMessage.payload['created_at'].as_string().desc(),GroundAssistantMessage.message_id).offset(offset).limit(limit))
    return [{'message':r.payload,'captured_at':r.captured_at,'received_at':r.received_at} for r in rows]
