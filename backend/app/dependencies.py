from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import RevokedToken, User

bearer_scheme = HTTPBearer()


def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id, jti = int(payload["sub"]), payload["jti"]
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise unauthorized
    if db.scalar(select(RevokedToken).where(RevokedToken.jti == jti)):
        raise unauthorized
    if not db.get(User, user_id):
        raise unauthorized
    return {"payload": payload, "token": credentials.credentials}


def get_current_user(token_data: dict = Depends(get_current_token), db: Session = Depends(get_db)) -> User:
    return db.get(User, int(token_data["payload"]["sub"]))


def token_expiry(payload: dict) -> datetime:
    return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
