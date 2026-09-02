from datetime import datetime, timezone

import jwt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, bearer_scheme
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import RevokedToken, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession):
    email = str(payload.email).lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)), user=user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession):
    user = db.scalar(select(User).where(func.lower(User.email) == str(payload.email).lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    return TokenResponse(access_token=create_access_token(str(user.id)), user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: DbSession, current_user: CurrentUser, credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]):
    # JWTs are stateless, so logout records their unique ID until expiry.
    try:
        payload = jwt.decode(credentials.credentials, get_settings().jwt_secret_key, algorithms=[get_settings().jwt_algorithm])
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        db.add(RevokedToken(jti=payload["jti"], expires_at=expires_at))
        db.commit()
    except (jwt.PyJWTError, KeyError):
        pass


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser):
    return current_user
