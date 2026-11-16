import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from ..database.db import get_db
from ..models.records import User, AuthSession, now

bearer = HTTPBearer(auto_error=False)

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 120_000).hex()
    return f'{salt}${digest}'

def password_matches(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split('$')[0]), stored)

def issue_token(db, user):
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                       expires_at=(datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()))
    db.commit()
    return token

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(401, 'Sign in required')
    session = db.get(AuthSession, hashlib.sha256(credentials.credentials.encode()).hexdigest())
    if not session or session.expires_at < now():
        raise HTTPException(401, 'Session expired or invalid')
    return db.get(User, session.user_id)

def astronaut(user=Depends(current_user)):
    if user.role != 'astronaut':
        raise HTTPException(403, 'Onboard astronaut access required')
    return user

def doctor(user=Depends(current_user)):
    if user.role != 'doctor':
        raise HTTPException(403, 'Doctor access required')
    return user

def own_record(user, user_id):
    if user.id != user_id:
        raise HTTPException(403, 'You may only access your onboard record')
