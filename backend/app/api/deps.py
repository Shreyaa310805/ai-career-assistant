from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import Plan, RevokedToken, User

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authentication token", headers={"WWW-Authenticate": "Bearer"})
    if not credentials or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, get_settings().jwt_secret_key, algorithms=[get_settings().jwt_algorithm])
        if payload.get("type") != "access" or not payload.get("sub") or not payload.get("jti"):
            raise unauthorized
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        raise unauthorized
    if db.get(RevokedToken, payload["jti"]):
        raise unauthorized
    user = db.get(User, user_id)
    if not user:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_premium(current_user: CurrentUser) -> User:
    if current_user.plan != Plan.PREMIUM:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This feature requires a PREMIUM plan")
    return current_user


PremiumUser = Annotated[User, Depends(require_premium)]
