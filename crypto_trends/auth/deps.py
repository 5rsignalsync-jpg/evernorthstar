"""FastAPI dependencies for auth.

`current_user` returns the logged-in User row or None (anonymous). Routes that
require auth use `require_user`; routes that gate on subscription tier use
`require_pro`. Anonymous browsing of /rankings etc. stays allowed — the
gating is per-tier in the response body, not at the route level (lets free
users see a teaser of Pro data).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request
from sqlmodel import Session

from crypto_trends.auth.db import get_session
from crypto_trends.auth.models import User
from crypto_trends.auth.tokens import decode_session
from crypto_trends.config import settings


def _cookie_token(request: Request) -> str | None:
    return request.cookies.get(settings.auth_cookie_name)


def current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> Optional[User]:
    """Resolves the current user from the session cookie. Returns None for anon."""
    token = _cookie_token(request)
    if not token:
        return None
    user_id = decode_session(token)
    if user_id is None:
        return None
    return session.get(User, user_id)


def require_user(user: Optional[User] = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(401, "Authentication required")
    return user


def is_pro(user: Optional[User]) -> bool:
    """A user is Pro if they have an active subscription_tier of pro/founder_lifetime
    AND their expiry (if set) is in the future. Founder lifetime has NULL expiry."""
    if user is None:
        return False
    if user.subscription_tier not in ("pro", "founder_lifetime"):
        return False
    if user.subscription_expires_at is None:
        return True  # founder lifetime, or stripe portal not yet wired
    return user.subscription_expires_at > datetime.now(tz=timezone.utc).replace(tzinfo=None)


def require_pro(user: User = Depends(require_user)) -> User:
    if not is_pro(user):
        raise HTTPException(402, "Pro subscription required")
    return user
