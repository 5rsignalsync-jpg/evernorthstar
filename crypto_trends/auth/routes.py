"""Auth HTTP routes: register, login, logout, me.

Sets the session as an httpOnly cookie so JS can't read it (mitigates XSS).
On secure deployments (HTTPS) the cookie should also be `Secure` — we toggle
that automatically based on the request scheme.
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from crypto_trends.auth.db import get_session
from crypto_trends.auth.deps import current_user, is_pro
from crypto_trends.auth.models import User
from crypto_trends.auth.passwords import hash_password, verify_password
from crypto_trends.auth.tokens import encode_session
from crypto_trends.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_NORMALIZE = re.compile(r"\s+")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    email: str
    subscription_tier: str
    subscription_expires_at: datetime | None
    is_pro: bool
    is_admin: bool


def _user_public(u: User) -> UserPublic:
    return UserPublic(
        id=u.id or 0,
        email=u.email,
        subscription_tier=u.subscription_tier,
        subscription_expires_at=u.subscription_expires_at,
        is_pro=is_pro(u),
        is_admin=u.is_admin,
    )


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    secure = request.url.scheme == "https"
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.jwt_expiration_days * 24 * 3600,
        path="/",
    )


@router.post("/register", response_model=UserPublic)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> UserPublic:
    email = EMAIL_NORMALIZE.sub("", body.email.strip().lower())
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(409, "An account with that email already exists")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        subscription_tier="free",
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = encode_session(user.id or 0)
    _set_session_cookie(response, request, token)
    return _user_public(user)


@router.post("/login", response_model=UserPublic)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> UserPublic:
    email = EMAIL_NORMALIZE.sub("", body.email.strip().lower())
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        # Generic message — don't leak whether the email exists
        raise HTTPException(401, "Invalid email or password")

    user.last_login_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)

    token = encode_session(user.id or 0)
    _set_session_cookie(response, request, token)
    return _user_public(user)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserPublic | None)
def me(user: User | None = Depends(current_user)) -> UserPublic | None:
    return _user_public(user) if user else None
