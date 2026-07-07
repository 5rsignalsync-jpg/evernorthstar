"""Admin-only endpoints for user management.

Gated on User.is_admin=True. Currently used to comp beta testers, family,
early customers, apology comps. Deliberately narrow surface — the wider
the admin API, the wider the blast radius of a compromised session.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from crypto_trends.auth.db import get_session
from crypto_trends.auth.deps import current_user
from crypto_trends.auth.models import User

router = APIRouter(prefix="/admin", tags=["admin"])
log = logging.getLogger(__name__)


def _require_admin(user: Optional[User]) -> User:
    if user is None:
        raise HTTPException(401, "Not authenticated")
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user


class CompRequest(BaseModel):
    email: EmailStr
    tier: str = Field(default="pro")  # 'pro' | 'founder_lifetime'
    note: Optional[str] = Field(default=None, max_length=200)


class CompResponse(BaseModel):
    email: str
    tier: str
    action: str  # 'promoted' | 'already_pro' | 'created_placeholder' | 'not_found'
    note: Optional[str] = None


@router.post("/comp", response_model=CompResponse)
def comp_user(
    payload: CompRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> CompResponse:
    """Grant lifetime Pro access (or founder_lifetime) to a user by email.

    If the user already has an account → promote them + null out expiry.
    If they don't → return not_found; the user should sign up first, at
    which point the comp allowlist (COMP_EMAILS env var) will handle them
    automatically. For durable one-off comps, add the email to COMP_EMAILS.

    Idempotent — running twice for the same email is a no-op.
    """
    _require_admin(user)
    if payload.tier not in ("pro", "founder_lifetime"):
        raise HTTPException(422, "tier must be 'pro' or 'founder_lifetime'")

    email = payload.email.lower().strip()
    target = session.exec(select(User).where(User.email == email)).first()
    if target is None:
        return CompResponse(
            email=email,
            tier=payload.tier,
            action="not_found",
            note="User has not signed up. Add to COMP_EMAILS env var or ask them to sign up first.",
        )
    if target.subscription_tier == payload.tier and target.subscription_expires_at is None:
        return CompResponse(email=email, tier=payload.tier, action="already_pro")
    target.subscription_tier = payload.tier
    target.subscription_expires_at = None
    session.add(target)
    session.commit()
    log.info(
        "admin_comp: %s comped %s to %s (note=%s)",
        user.email, email, payload.tier, payload.note,
    )
    return CompResponse(
        email=email,
        tier=payload.tier,
        action="promoted",
        note=payload.note,
    )


class UncompRequest(BaseModel):
    email: EmailStr


@router.post("/uncomp", response_model=CompResponse)
def uncomp_user(
    payload: UncompRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> CompResponse:
    """Reverse a comp — set user back to free tier.

    Use for: revoking access to bad-actor testers, correcting mistakes.
    Does NOT affect paying customers (their tier tracks Stripe webhook state).
    """
    _require_admin(user)
    email = payload.email.lower().strip()
    target = session.exec(select(User).where(User.email == email)).first()
    if target is None:
        return CompResponse(
            email=email, tier="free", action="not_found"
        )
    if target.subscription_tier == "free":
        return CompResponse(email=email, tier="free", action="already_pro")
    target.subscription_tier = "free"
    target.subscription_expires_at = None
    session.add(target)
    session.commit()
    log.info("admin_uncomp: %s uncomped %s", user.email, email)
    return CompResponse(email=email, tier="free", action="promoted")


class AdminUserSummary(BaseModel):
    id: int
    email: str
    subscription_tier: str
    subscription_expires_at: Optional[datetime]
    is_admin: bool
    created_at: datetime
    last_login_at: Optional[datetime]


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(
    limit: int = 100,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[AdminUserSummary]:
    """List the most-recently-signed-up users. Useful for spot-checking
    who's on the platform and what tier they hold. Capped at 500 to keep
    payloads modest."""
    _require_admin(user)
    limit = max(1, min(limit, 500))
    rows = session.exec(
        select(User).order_by(User.created_at.desc()).limit(limit)
    ).all()
    return [
        AdminUserSummary(
            id=r.id or 0,
            email=r.email,
            subscription_tier=r.subscription_tier,
            subscription_expires_at=r.subscription_expires_at,
            is_admin=r.is_admin,
            created_at=r.created_at,
            last_login_at=r.last_login_at,
        )
        for r in rows
    ]
