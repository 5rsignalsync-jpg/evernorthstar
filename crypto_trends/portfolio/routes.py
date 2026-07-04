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
from crypto_trends.portfolio import analysis, planning, plaid_client, sync
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
    id: Optional[int] = None
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


# ---------------- Position planning (Sprint 1 + 2) ----------------

class ZoneReadingOut(BaseModel):
    zone: str
    zone_confidence: float
    rsi: Optional[float] = None
    bb_position_sigma: Optional[float] = None
    score_percentile: Optional[float] = None
    volume_divergence: bool
    accumulation_low: Optional[float] = None
    accumulation_high: Optional[float] = None
    distribution_low: Optional[float] = None
    distribution_high: Optional[float] = None
    current_price: Optional[float] = None


class RingFenceScenarioOut(BaseModel):
    pct_of_gain_locked: float
    amount_to_take_usd: float
    remaining_position_value: float
    net_pl_if_remainder_zero_usd: float


class HistoricalOutcomeOut(BaseModel):
    ticker: str
    setup_date: str
    setup_price: float
    fwd_30d_return_pct: Optional[float] = None
    fwd_90d_return_pct: Optional[float] = None


class HistoricalStatsOut(BaseModel):
    n_setups: int
    median_fwd_30d_return_pct: Optional[float] = None
    median_fwd_90d_return_pct: Optional[float] = None
    p25_fwd_30d_return_pct: Optional[float] = None
    p75_fwd_30d_return_pct: Optional[float] = None
    sample: list[HistoricalOutcomeOut] = []


class PositionPlanOut(BaseModel):
    symbol: str
    base: str
    asset_class: str
    quantity: float
    cost_basis_per_share: Optional[float] = None
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    unrealized_gain_usd: Optional[float] = None
    unrealized_gain_pct: Optional[float] = None
    zone: ZoneReadingOut
    ring_fence_scenarios: list[RingFenceScenarioOut]
    historical: Optional[HistoricalStatsOut] = None
    # Legal safety marker — every planning payload must carry the same
    # descriptive-not-prescriptive framing at the API layer.
    disclaimer: str = (
        "Data-descriptive planning tool. Not investment advice. Zone labels "
        "describe technical setup only. Historical outcome distributions "
        "reflect past behavior and do not predict future results. You are "
        "solely responsible for any decisions you make from this data."
    )


def _plan_to_out(plan: planning.PositionPlan) -> PositionPlanOut:
    zr = plan.zone
    hist_out: Optional[HistoricalStatsOut] = None
    if plan.historical is not None:
        hist_out = HistoricalStatsOut(
            n_setups=plan.historical.n_setups,
            median_fwd_30d_return_pct=plan.historical.median_fwd_30d_return_pct,
            median_fwd_90d_return_pct=plan.historical.median_fwd_90d_return_pct,
            p25_fwd_30d_return_pct=plan.historical.p25_fwd_30d_return_pct,
            p75_fwd_30d_return_pct=plan.historical.p75_fwd_30d_return_pct,
            sample=[HistoricalOutcomeOut(**o.__dict__) for o in plan.historical.sample],
        )
    return PositionPlanOut(
        symbol=plan.symbol,
        base=plan.base,
        asset_class=plan.asset_class,
        quantity=plan.quantity,
        cost_basis_per_share=plan.cost_basis_per_share,
        current_price=plan.current_price,
        current_value=plan.current_value,
        unrealized_gain_usd=plan.unrealized_gain_usd,
        unrealized_gain_pct=plan.unrealized_gain_pct,
        zone=ZoneReadingOut(
            zone=zr.zone,
            zone_confidence=zr.zone_confidence,
            rsi=zr.rsi,
            bb_position_sigma=zr.bb_position_sigma,
            score_percentile=zr.score_percentile,
            volume_divergence=zr.volume_divergence,
            accumulation_low=zr.accumulation_low,
            accumulation_high=zr.accumulation_high,
            distribution_low=zr.distribution_low,
            distribution_high=zr.distribution_high,
            current_price=zr.current_price,
        ),
        ring_fence_scenarios=[
            RingFenceScenarioOut(**s.__dict__) for s in plan.ring_fence_scenarios
        ],
        historical=hist_out,
    )


@router.get("/holdings/{holding_id}/plan", response_model=PositionPlanOut)
def get_holding_plan(
    holding_id: int,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> PositionPlanOut:
    """Position plan for one of the user's Plaid-synced holdings.

    Uses the holding's cost basis (from Plaid) to power the ring-fence
    scenarios; combines with market-side zone + historical outcomes.
    """
    holding = session.get(Holding, holding_id)
    if holding is None or holding.user_id != user.id:
        raise HTTPException(404, "Holding not found")

    # Resolve base symbol: for crypto, Plaid may hand us a bare ticker
    # ('BTC') while our universe stores 'BTCUSDT'. Try both.
    symbol_candidates = [holding.ticker or ""]
    if holding.ticker and not holding.ticker.endswith("USDT"):
        symbol_candidates.append(f"{holding.ticker}USDT")
    plan = None
    for sym in symbol_candidates:
        if not sym:
            continue
        plan = planning.build_position_plan(
            symbol=sym,
            base=holding.ticker or sym,
            asset_class=holding.security_type or "unknown",
            quantity=holding.quantity,
            cost_basis_per_share=(
                holding.cost_basis / holding.quantity
                if holding.cost_basis and holding.quantity
                else None
            ),
        )
        if plan is not None:
            break
    if plan is None:
        raise HTTPException(
            424,
            "No price history for this ticker. Planning is currently limited to "
            "assets in our tracked universe.",
        )
    return _plan_to_out(plan)


@router.get("/plan/{symbol}", response_model=PositionPlanOut)
def get_symbol_plan(
    symbol: str,
    quantity: float = 1.0,
    cost_basis_per_share: Optional[float] = None,
    user: User = Depends(require_pro),
) -> PositionPlanOut:
    """Position plan for an arbitrary symbol (not tied to a Plaid holding).

    Lets Pro users explore the planning tool for tickers they don't hold
    via Plaid, or for hypothetical positions.
    """
    plan = planning.build_position_plan(
        symbol=symbol,
        base=symbol,
        asset_class="unknown",
        quantity=quantity,
        cost_basis_per_share=cost_basis_per_share,
    )
    if plan is None:
        raise HTTPException(
            424,
            "No price history found for this symbol. Try a ticker in our tracked universe.",
        )
    return _plan_to_out(plan)
