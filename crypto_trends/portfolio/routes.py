"""Portfolio HTTP routes — Plaid Link flow + holdings view.

All routes require Pro tier (portfolio sync is the headline Pro feature).
Plaid endpoints return 503 'feature pending' if Plaid creds aren't set,
so deployments without Plaid still serve cleanly.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from crypto_trends.auth.db import get_session
from crypto_trends.auth.deps import require_pro
from crypto_trends.auth.models import User
from crypto_trends.portfolio import analysis, plaid_client, sync
from crypto_trends.portfolio.encryption import encrypt_token
from crypto_trends.portfolio.models import BrokerageAccount, Holding

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
log = logging.getLogger(__name__)


# ---------------- Pydantic response models ----------------

class LinkTokenResponse(BaseModel):
    link_token: str
    env: str


class ExchangeTokenRequest(BaseModel):
    public_token: str


class BrokerageAccountOut(BaseModel):
    id: int
    institution_name: str
    status: str
    last_synced_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime


class AnnotatedHoldingOut(BaseModel):
    ticker: Optional[str]
    name: str
    security_type: Optional[str]
    quantity: float
    value: Optional[float]
    cost_basis: Optional[float]
    institution_name: str
    momentum_score: Optional[float]
    asset_class: Optional[str]
    smart_money_actors: list[str]
    smart_money_buys_usd: float
    smart_money_sells_usd: float


class PortfolioSummaryOut(BaseModel):
    total_value_usd: float
    n_holdings: int
    n_with_signal: int
    n_with_smart_money: int
    weighted_momentum_score: Optional[float]
    smart_money_overlap_pct: float
    momentum_quality_label: str


class PortfolioResponse(BaseModel):
    summary: PortfolioSummaryOut
    holdings: list[AnnotatedHoldingOut]
    accounts: list[BrokerageAccountOut]
    plaid_enabled: bool


# ---------------- Plaid feature gate ----------------

def _require_plaid_configured():
    if not plaid_client.is_enabled():
        raise HTTPException(
            503,
            "Brokerage sync is coming soon — this deployment hasn't been "
            "provisioned with Plaid credentials yet.",
        )


# ---------------- Routes ----------------

@router.post("/link-token", response_model=LinkTokenResponse)
def create_link_token(
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> LinkTokenResponse:
    """Returns a Plaid Link token the frontend uses to open Plaid's modal."""
    _require_plaid_configured()
    try:
        from crypto_trends.config import settings
        token = plaid_client.create_link_token(user.id or 0, user.email)
        return LinkTokenResponse(link_token=token, env=settings.plaid_env)
    except Exception as e:
        log.exception("link-token failed for user %s", user.id)
        raise HTTPException(502, f"Plaid link token creation failed: {e}")


@router.post("/exchange-token", response_model=BrokerageAccountOut, status_code=201)
def exchange_token(
    payload: ExchangeTokenRequest,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> BrokerageAccountOut:
    """Exchange the public_token returned by Plaid Link for a long-lived
    access_token and persist the new BrokerageAccount."""
    _require_plaid_configured()
    try:
        exchanged = plaid_client.exchange_public_token(payload.public_token)
    except Exception as e:
        log.exception("exchange failed for user %s", user.id)
        raise HTTPException(502, f"Plaid token exchange failed: {e}")

    # Guard against duplicate item — if the user re-links the same institution,
    # update the existing row instead of inserting a parallel one.
    existing = session.exec(
        select(BrokerageAccount).where(
            BrokerageAccount.plaid_item_id == exchanged.item_id
        )
    ).first()

    if existing:
        if existing.user_id != user.id:
            # Should never happen — same plaid item_id is unique to one user.
            raise HTTPException(409, "Item already belongs to a different user.")
        existing.access_token_encrypted = encrypt_token(exchanged.access_token)
        existing.status = "active"
        existing.last_error = None
        session.add(existing)
        session.commit()
        session.refresh(existing)
        account = existing
    else:
        account = BrokerageAccount(
            user_id=user.id or 0,
            plaid_item_id=exchanged.item_id,
            access_token_encrypted=encrypt_token(exchanged.access_token),
            institution_id=exchanged.institution_id,
            institution_name=exchanged.institution_name,
            status="active",
        )
        session.add(account)
        session.commit()
        session.refresh(account)

    # Kick off an immediate sync so the user sees holdings right away.
    # Errors here don't roll back the link — they just leave holdings empty
    # until the next cron run.
    try:
        sync.sync_account(account.id or 0)
        session.refresh(account)
    except Exception as e:
        log.warning("initial sync after link failed: %s", e)

    return BrokerageAccountOut(
        id=account.id or 0,
        institution_name=account.institution_name,
        status=account.status,
        last_synced_at=account.last_synced_at,
        last_error=account.last_error,
        created_at=account.created_at,
    )


@router.delete("/accounts/{account_id}", status_code=204)
def disconnect_account(
    account_id: int,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> None:
    """Disconnect a brokerage: revoke Plaid item + delete account + holdings."""
    account = session.get(BrokerageAccount, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Brokerage account not found")
    if plaid_client.is_enabled():
        try:
            from crypto_trends.portfolio.encryption import decrypt_token
            token = decrypt_token(account.access_token_encrypted)
            plaid_client.remove_item(token)
        except Exception as e:
            log.warning("plaid remove failed (proceeding with local delete): %s", e)
    # Cascade-delete holdings, then the account row.
    from sqlmodel import delete as sa_delete
    session.exec(sa_delete(Holding).where(Holding.account_id == account_id))
    session.delete(account)
    session.commit()


@router.post("/sync/{account_id}", response_model=BrokerageAccountOut)
def manual_sync(
    account_id: int,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> BrokerageAccountOut:
    """Manual refresh button on the UI — also useful for ops debugging."""
    _require_plaid_configured()
    account = session.get(BrokerageAccount, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Brokerage account not found")
    sync.sync_account(account_id)
    session.refresh(account)
    return BrokerageAccountOut(
        id=account.id or 0,
        institution_name=account.institution_name,
        status=account.status,
        last_synced_at=account.last_synced_at,
        last_error=account.last_error,
        created_at=account.created_at,
    )


@router.get("", response_model=PortfolioResponse)
def get_portfolio(
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> PortfolioResponse:
    """The full portfolio view — accounts + annotated holdings + summary.

    Returns even when no brokerages are connected (empty summary) so the
    frontend can render the 'connect your first brokerage' empty state.
    Plaid creds NOT required to call this — it reads from our DB.
    """
    summary, annotated = analysis.analyze_user_portfolio(user.id or 0)
    accounts = session.exec(
        select(BrokerageAccount).where(BrokerageAccount.user_id == user.id)
    ).all()

    return PortfolioResponse(
        summary=PortfolioSummaryOut(
            total_value_usd=summary.total_value_usd,
            n_holdings=summary.n_holdings,
            n_with_signal=summary.n_with_signal,
            n_with_smart_money=summary.n_with_smart_money,
            weighted_momentum_score=summary.weighted_momentum_score,
            smart_money_overlap_pct=summary.smart_money_overlap_pct,
            momentum_quality_label=summary.momentum_quality_label,
        ),
        holdings=[AnnotatedHoldingOut(**a.__dict__) for a in annotated],
        accounts=[
            BrokerageAccountOut(
                id=a.id or 0,
                institution_name=a.institution_name,
                status=a.status,
                last_synced_at=a.last_synced_at,
                last_error=a.last_error,
                created_at=a.created_at,
            )
            for a in accounts
        ],
        plaid_enabled=plaid_client.is_enabled(),
    )
