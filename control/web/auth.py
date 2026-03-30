"""
Session-based authentication using itsdangerous signed cookies.
"""

import os
from functools import wraps
from typing import Optional

import bcrypt
from fastapi import Cookie, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from control.db.models import User

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please")
_serializer = URLSafeTimedSerializer(SECRET_KEY)
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_session_token(user_id: str) -> str:
    return _serializer.dumps(user_id, salt="session")


def decode_session_token(token: str) -> Optional[str]:
    try:
        return _serializer.loads(token, salt="session", max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def set_session_cookie(response, user_id: str):
    token = create_session_token(user_id)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )


def clear_session_cookie(response):
    response.delete_cookie("session")


def get_current_user(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get("session")
    if not token:
        return None
    user_id = decode_session_token(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_login(request: Request, db: Session) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/login"},
        )
    return user


def create_user(db: Session, email: str, password: str, is_admin: bool = False) -> User:
    user = User(email=email, password_hash=hash_password(password), is_admin=is_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
