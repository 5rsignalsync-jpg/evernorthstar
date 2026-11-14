"""Admin-only endpoints for user management + on-demand data refresh.

Gated on User.is_admin=True. Currently used to comp beta testers, family,
early customers, apology comps. Deliberately narrow surface — the wider
the admin API, the wider the blast radius of a compromised session.

The /admin/refresh endpoints let the admin trigger a data refresh without
depending on GitHub Actions (which auto-disables after 60 days of repo
inactivity). Refresh runs in a background thread so the HTTP response is
instant; /admin/refresh/status polls for completion.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from crypto_trends.auth.db import get_session
from crypto_trends.auth.deps import current_user
from crypto_trends.auth.models import User

router = APIRouter(prefix="/admin", tags=["admin"])
log = logging.getLogger(__name__)


# ---------------- Refresh job state (process-local) ----------------
# A single Fly machine runs the API with one uvicorn worker (SQLite
# constraint — see C4), so a module-level dict is safe and correct here.
# If we ever scale to multiple machines, move this to Redis.
_REFRESH_STATE: dict = {
    "status": "idle",          # 'idle' | 'running' | 'success' | 'failed'
    "scope": None,             # 'equities' | 'crypto' | 'all'
    "started_at": None,
    "completed_at": None,
    "error": None,
    "started_by": None,        # admin email
    "phases": [],              # list of phase result dicts
}
_REFRESH_LOCK = threading.Lock()


def _run_refresh(scope: str, started_by: str) -> None:
    """Background worker: runs scripts.refresh_all and updates _REFRESH_STATE.
    Catches ALL exceptions so a bad run doesn't leave status stuck on
    'running' forever."""
    from crypto_trends.logging_config import configure
    configure()
    log.info("admin refresh started scope=%s by=%s", scope, started_by)

    args = []
    if scope == "crypto":
        args = ["--crypto-only"]
    elif scope == "equities":
        # Skip crypto (it has its own 15-min APScheduler cron) + skip news
        # (FinBERT is too heavy for the 1GB Fly machine; news runs locally
        # on launchd per project memory).
        args = ["--skip-crypto", "--skip-news"]
    # 'all' = no args, full pipeline

    try:
        # Build argv for refresh_all.main() rather than invoking as subprocess.
        import sys as _sys
        prior_argv = _sys.argv
        _sys.argv = ["refresh_all", *args]
        from scripts.refresh_all import main as refresh_main
        exit_code = refresh_main()
        _sys.argv = prior_argv

        with _REFRESH_LOCK:
            _REFRESH_STATE["status"] = "success" if exit_code == 0 else "failed"
            _REFRESH_STATE["completed_at"] = datetime.utcnow()
            if exit_code != 0:
                _REFRESH_STATE["error"] = f"Refresh completed with exit code {exit_code}"
        log.info("admin refresh completed scope=%s exit=%s", scope, exit_code)
    except Exception as e:
        log.exception("admin refresh failed scope=%s", scope)
        with _REFRESH_LOCK:
            _REFRESH_STATE["status"] = "failed"
            _REFRESH_STATE["completed_at"] = datetime.utcnow()
            _REFRESH_STATE["error"] = str(e)[:500]


class RefreshRequest(BaseModel):
    scope: Literal["crypto", "equities", "all"] = "equities"


class RefreshStatusOut(BaseModel):
    status: Literal["idle", "running", "success", "failed"]
    scope: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    started_by: Optional[str]
    seconds_elapsed: Optional[float]


@router.post("/refresh", response_model=RefreshStatusOut)
def trigger_refresh(
    payload: RefreshRequest,
    user: User = Depends(current_user),
) -> RefreshStatusOut:
    """Admin-triggered data refresh. Runs in a background thread so the
    HTTP response is instant. Only one refresh can run at a time; a
    10-minute cooldown prevents thrash between successful runs."""
    _require_admin(user)

    with _REFRESH_LOCK:
        if _REFRESH_STATE["status"] == "running":
            raise HTTPException(
                409,
                f"A refresh is already running (started {_REFRESH_STATE['started_at']} "
                f"by {_REFRESH_STATE['started_by']}). Wait for it to finish.",
            )
        # 10-min cooldown between successful completions (prevents thrash,
        # per-scope). Failures don't trigger cooldown — fix-and-retry is OK.
        if (
            _REFRESH_STATE["status"] == "success"
            and _REFRESH_STATE["scope"] == payload.scope
            and _REFRESH_STATE["completed_at"] is not None
            and (datetime.utcnow() - _REFRESH_STATE["completed_at"]) < timedelta(minutes=10)
        ):
            raise HTTPException(
                429,
                f"'{payload.scope}' refresh succeeded less than 10 minutes ago. "
                f"Try again after {_REFRESH_STATE['completed_at'] + timedelta(minutes=10)}.",
            )
        now = datetime.utcnow()
        _REFRESH_STATE.update({
            "status": "running",
            "scope": payload.scope,
            "started_at": now,
            "completed_at": None,
            "error": None,
            "started_by": user.email,
            "phases": [],
        })

    t = threading.Thread(
        target=_run_refresh,
        args=(payload.scope, user.email),
        daemon=True,
        name=f"admin-refresh-{payload.scope}",
    )
    t.start()

    return _build_status_out()


@router.get("/refresh/status", response_model=RefreshStatusOut)
def refresh_status(user: User = Depends(current_user)) -> RefreshStatusOut:
    """Current refresh status. Any Pro user can view (so admins can see
    progress from any device); only admins can trigger."""
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return _build_status_out()


def _build_status_out() -> RefreshStatusOut:
    with _REFRESH_LOCK:
        elapsed = None
        if _REFRESH_STATE["started_at"]:
            end = _REFRESH_STATE["completed_at"] or datetime.utcnow()
            elapsed = (end - _REFRESH_STATE["started_at"]).total_seconds()
        return RefreshStatusOut(
            status=_REFRESH_STATE["status"],
            scope=_REFRESH_STATE["scope"],
            started_at=_REFRESH_STATE["started_at"],
            completed_at=_REFRESH_STATE["completed_at"],
            error=_REFRESH_STATE["error"],
            started_by=_REFRESH_STATE["started_by"],
            seconds_elapsed=elapsed,
        )


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
