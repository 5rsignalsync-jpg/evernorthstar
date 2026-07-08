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
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from crypto_trends.auth.db import get_session
from crypto_trends.auth.deps import require_pro
from crypto_trends.auth.models import User, AlertRule
from crypto_trends.portfolio import analysis, planning, plaid_client, sync
from crypto_trends.portfolio.encryption import encrypt_token
from crypto_trends.portfolio.models import BrokerageAccount, CryptoRealization, Holding

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
    # Tax estimate fields. is_long_term reflects the position's holding
    # period at plan time (≥365 days). Rates are US federal + CO state
    # defaults; higher/lower-bracket users may want to interpret the number
    # against their own situation — flagged in the UI copy.
    is_long_term: bool = False
    tax_rate_applied_pct: float = 0.0
    tax_owed_usd: float = 0.0
    net_after_tax_usd: float = 0.0


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


class EntryTrancheOut(BaseModel):
    label: str
    price: float
    pct_of_budget: float
    amount_usd: Optional[float] = None
    quantity: Optional[float] = None


class EntryPlanOut(BaseModel):
    status: str
    accumulation_low: float
    accumulation_high: float
    invalidation_level: float
    tranches: list[EntryTrancheOut]
    note: str


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
    entry_plan: Optional[EntryPlanOut] = None
    historical: Optional[HistoricalStatsOut] = None
    ai_summary: Optional[str] = None
    ai_enabled: bool = False
    # Legal safety marker — every planning payload must carry the same
    # descriptive-not-prescriptive framing at the API layer.
    disclaimer: str = (
        "Data-descriptive planning tool. Not investment advice. Zone labels "
        "describe technical setup only. Historical outcome distributions "
        "reflect past behavior and do not predict future results. You are "
        "solely responsible for any decisions you make from this data."
    )


def _plan_to_out(
    plan: planning.PositionPlan, with_ai: bool = False
) -> PositionPlanOut:
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

    # Lazy-import the AI module to avoid an unconditional dependency at boot.
    from crypto_trends.ai import claude as claude_mod
    ai_enabled = claude_mod.is_enabled()
    ai_summary: Optional[str] = None
    if with_ai and ai_enabled:
        from crypto_trends.ai.position_summary import summarize_plan
        try:
            ai_summary = summarize_plan(plan)
        except Exception:
            log.exception("AI position summary failed for %s", plan.symbol)

    ep = plan.entry_plan
    entry_out: Optional[EntryPlanOut] = None
    if ep is not None:
        entry_out = EntryPlanOut(
            status=ep.status,
            accumulation_low=ep.accumulation_low,
            accumulation_high=ep.accumulation_high,
            invalidation_level=ep.invalidation_level,
            tranches=[EntryTrancheOut(**t.__dict__) for t in ep.tranches],
            note=ep.note,
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
        entry_plan=entry_out,
        historical=hist_out,
        ai_summary=ai_summary,
        ai_enabled=ai_enabled,
    )


@router.get("/holdings/{holding_id}/plan", response_model=PositionPlanOut)
def get_holding_plan(
    holding_id: int,
    with_ai: bool = False,
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
            # Plaid Holdings are snapshots overwritten on each sync — Plaid's
            # Investments product doesn't expose the actual purchase date, so
            # we can't derive an accurate holding period here. Passing None
            # falls back to the conservative short-term rate; users on real
            # long-term positions will want to override at the UI layer or
            # confirm with their own broker's cost-basis report.
            position_acquired_at=None,
        )
        if plan is not None:
            break
    if plan is None:
        raise HTTPException(
            424,
            "No price history for this ticker. Planning is currently limited to "
            "assets in our tracked universe.",
        )
    return _plan_to_out(plan, with_ai=with_ai)


# ---------------- Arm plan → alerts (Sprint 3) ----------------

_PLAN_ALERT_PREFIX = "PLAN:"  # marks alerts created by "arm this plan"


class ArmedAlertOut(BaseModel):
    condition: str
    threshold: float
    note: str


class ArmPlanResponse(BaseModel):
    symbol: str
    armed: int
    replaced: int
    alerts: list[ArmedAlertOut]
    # Same descriptive-not-prescriptive posture as the plan itself.
    disclaimer: str = (
        "These are price alerts at levels from your plan, not orders or advice. "
        "You decide whether to act when one fires."
    )


@router.post("/holdings/{holding_id}/plan/arm", response_model=ArmPlanResponse)
def arm_holding_plan(
    holding_id: int,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> ArmPlanResponse:
    """Arm a holding's plan: create price alerts at every decision level —
    each entry rung, the invalidation, and the profit-taking zone — so the
    user is pinged at those levels instead of watching charts. Re-arming
    replaces the plan's prior alerts for this symbol. Data-driven, not advice.
    """
    holding = session.get(Holding, holding_id)
    if holding is None or holding.user_id != user.id:
        raise HTTPException(404, "Holding not found")

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
        raise HTTPException(424, "No price history for this ticker.")

    # Collect (condition, threshold, label) for every level in the plan.
    levels: list[tuple[str, float, str]] = []
    ep = plan.entry_plan
    if ep is not None:
        for t in ep.tranches:
            levels.append(("price_below", t.price, f"entry · {t.label}"))
        levels.append(("price_below", ep.invalidation_level, "invalidation"))
    zr = plan.zone
    if zr.distribution_low is not None:
        levels.append(("price_above", zr.distribution_low, "take-profit · zone start"))
    if zr.distribution_high is not None:
        levels.append(("price_above", zr.distribution_high, "take-profit · zone end"))

    if not levels:
        raise HTTPException(
            422, "This plan has no armable levels yet (needs an accumulation zone)."
        )

    symbol_up = plan.symbol.upper()
    # Replace any prior plan-armed alerts for this symbol (idempotent re-arm).
    prior = session.exec(
        select(AlertRule).where(
            (AlertRule.user_id == user.id)
            & (AlertRule.symbol == symbol_up)
            & (AlertRule.note.like(f"{_PLAN_ALERT_PREFIX}%"))  # type: ignore[union-attr]
        )
    ).all()
    for r in prior:
        session.delete(r)

    created: list[ArmedAlertOut] = []
    for condition, threshold, label in levels:
        note = f"{_PLAN_ALERT_PREFIX} {label}"[:200]
        session.add(AlertRule(
            user_id=user.id or 0,
            symbol=symbol_up,
            asset_class=plan.asset_class,
            condition=condition,
            threshold=float(threshold),
            zone_target=None,
            note=note,
            enabled=True,
        ))
        created.append(
            ArmedAlertOut(condition=condition, threshold=float(threshold), note=note)
        )
    session.commit()
    return ArmPlanResponse(
        symbol=symbol_up, armed=len(created), replaced=len(prior), alerts=created
    )


@router.get("/plan/{symbol}", response_model=PositionPlanOut)
def get_symbol_plan(
    symbol: str,
    quantity: float = 1.0,
    cost_basis_per_share: Optional[float] = None,
    with_ai: bool = False,
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
    return _plan_to_out(plan, with_ai=with_ai)


# ---------------- Manual crypto positions (Sprint 4) ----------------

from crypto_trends.portfolio.models import CryptoPosition
from crypto_trends.data.store import connect as _duck_connect


class CryptoPositionIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    quantity: float = Field(gt=0)
    cost_basis_per_share: float = Field(gt=0)
    exchange_label: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=500)


class CryptoPositionOut(BaseModel):
    id: int
    symbol: str
    quantity: float
    cost_basis_per_share: float
    exchange_label: Optional[str]
    notes: Optional[str]
    total_cost_usd: float
    current_price: Optional[float]
    current_value_usd: Optional[float]
    unrealized_gain_usd: Optional[float]
    unrealized_gain_pct: Optional[float]
    created_at: datetime
    updated_at: datetime


def _current_price_for_crypto(symbol: str) -> Optional[float]:
    """Pull the latest close from ohlcv. Tries bare BTC and BTCUSDT variants."""
    candidates = [symbol.upper()]
    if not symbol.upper().endswith("USDT"):
        candidates.append(f"{symbol.upper()}USDT")
    with _duck_connect(read_only=True) as conn:
        for sym in candidates:
            row = conn.execute(
                "SELECT close FROM ohlcv WHERE symbol = ? ORDER BY ts DESC LIMIT 1",
                [sym],
            ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
    return None


def _crypto_position_to_out(p: CryptoPosition) -> CryptoPositionOut:
    total_cost = p.quantity * p.cost_basis_per_share
    price = _current_price_for_crypto(p.symbol)
    value = (price * p.quantity) if price is not None else None
    gain = (value - total_cost) if value is not None else None
    gain_pct = (
        ((price / p.cost_basis_per_share) - 1) * 100
        if price is not None and p.cost_basis_per_share > 0
        else None
    )
    return CryptoPositionOut(
        id=p.id or 0,
        symbol=p.symbol,
        quantity=p.quantity,
        cost_basis_per_share=p.cost_basis_per_share,
        exchange_label=p.exchange_label,
        notes=p.notes,
        total_cost_usd=total_cost,
        current_price=price,
        current_value_usd=value,
        unrealized_gain_usd=gain,
        unrealized_gain_pct=gain_pct,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/crypto/positions", response_model=list[CryptoPositionOut])
def list_crypto_positions(
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> list[CryptoPositionOut]:
    """List all manual crypto positions for the current Pro user, ordered
    by current value descending so the biggest bags surface first."""
    rows = session.exec(
        select(CryptoPosition)
        .where(CryptoPosition.user_id == user.id)
        .order_by(CryptoPosition.created_at.desc())
    ).all()
    outs = [_crypto_position_to_out(r) for r in rows]
    outs.sort(key=lambda o: o.current_value_usd or 0.0, reverse=True)
    return outs


@router.post("/crypto/positions", response_model=CryptoPositionOut, status_code=201)
def create_crypto_position(
    payload: CryptoPositionIn,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> CryptoPositionOut:
    pos = CryptoPosition(
        user_id=user.id or 0,
        symbol=payload.symbol.strip().upper(),
        quantity=payload.quantity,
        cost_basis_per_share=payload.cost_basis_per_share,
        exchange_label=(payload.exchange_label or "").strip() or None,
        notes=(payload.notes or "").strip() or None,
    )
    session.add(pos)
    session.commit()
    session.refresh(pos)
    return _crypto_position_to_out(pos)


@router.patch("/crypto/positions/{pos_id}", response_model=CryptoPositionOut)
def update_crypto_position(
    pos_id: int,
    payload: CryptoPositionIn,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> CryptoPositionOut:
    pos = session.get(CryptoPosition, pos_id)
    if pos is None or pos.user_id != user.id:
        raise HTTPException(404, "Crypto position not found")
    pos.symbol = payload.symbol.strip().upper()
    pos.quantity = payload.quantity
    pos.cost_basis_per_share = payload.cost_basis_per_share
    pos.exchange_label = (payload.exchange_label or "").strip() or None
    pos.notes = (payload.notes or "").strip() or None
    pos.updated_at = datetime.utcnow()
    session.add(pos)
    session.commit()
    session.refresh(pos)
    return _crypto_position_to_out(pos)


@router.delete("/crypto/positions/{pos_id}", status_code=204)
def delete_crypto_position(
    pos_id: int,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> None:
    pos = session.get(CryptoPosition, pos_id)
    if pos is None or pos.user_id != user.id:
        raise HTTPException(404, "Crypto position not found")
    session.delete(pos)
    session.commit()


# ---------------- Crypto position plan (tax-aware) ----------------

@router.get("/crypto/positions/{pos_id}/plan", response_model=PositionPlanOut)
def get_crypto_position_plan(
    pos_id: int,
    with_ai: bool = False,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> PositionPlanOut:
    """Position plan for a manually-entered crypto position.

    Uses the position's created_at as the acquisition date so the ring-fence
    tax fields reflect the actual holding period (long-term vs short-term).
    Symbol resolution mirrors the Plaid holding path — 'BTC' → 'BTCUSDT'
    when needed to hit the tracked universe.
    """
    pos = session.get(CryptoPosition, pos_id)
    if pos is None or pos.user_id != user.id:
        raise HTTPException(404, "Crypto position not found")

    candidates = [pos.symbol]
    if not pos.symbol.endswith("USDT"):
        candidates.append(f"{pos.symbol}USDT")
    plan = None
    for sym in candidates:
        plan = planning.build_position_plan(
            symbol=sym,
            base=pos.symbol,
            asset_class="crypto",
            quantity=pos.quantity,
            cost_basis_per_share=pos.cost_basis_per_share,
            position_acquired_at=pos.created_at,
        )
        if plan is not None:
            break
    if plan is None:
        raise HTTPException(
            424,
            "No price history for this symbol. Planning is currently limited "
            "to assets in our tracked universe.",
        )
    return _plan_to_out(plan, with_ai=with_ai)


# ---------------- Mark-as-sold (realizations ledger) ----------------

# Tax constants mirror crypto_trends.portfolio.planning defaults. When
# planning eventually gains a user-preference override, both should read
# from the same source rather than duplicating this constant.
_FED_LT_RATE = 0.15
_FED_ST_RATE = 0.22
_STATE_RATE = 0.044
_LONG_TERM_DAYS = 365


class RealizeIn(BaseModel):
    quantity_sold: float = Field(gt=0)
    price_sold: float = Field(gt=0)
    sold_at: Optional[datetime] = None       # None → now
    note: Optional[str] = Field(default=None, max_length=200)


class RealizationOut(BaseModel):
    id: int
    position_id: int
    symbol: str
    quantity_sold: float
    price_sold: float
    cost_basis_per_share_at_sale: float
    realized_pl_usd: float
    is_long_term: bool
    tax_owed_usd_est: float
    net_after_tax_usd: float
    sold_at: datetime
    note: Optional[str]
    created_at: datetime


class RealizeResponse(BaseModel):
    realization: RealizationOut
    remaining_quantity: float                 # after the sale
    position_closed: bool                     # true when remaining_quantity == 0
    disclaimer: str = (
        "Tax figures are estimates using default US federal + Colorado state "
        "rates. Consult a tax professional for your specific situation."
    )


def _realization_to_out(r: CryptoRealization, symbol: str) -> RealizationOut:
    return RealizationOut(
        id=r.id or 0,
        position_id=r.position_id,
        symbol=symbol,
        quantity_sold=r.quantity_sold,
        price_sold=r.price_sold,
        cost_basis_per_share_at_sale=r.cost_basis_per_share_at_sale,
        realized_pl_usd=r.realized_pl_usd,
        is_long_term=r.is_long_term,
        tax_owed_usd_est=r.tax_owed_usd_est,
        net_after_tax_usd=(r.quantity_sold * r.price_sold) - r.tax_owed_usd_est,
        sold_at=r.sold_at,
        note=r.note,
        created_at=r.created_at,
    )


@router.post(
    "/crypto/positions/{pos_id}/realize",
    response_model=RealizeResponse,
    status_code=201,
)
def realize_crypto_position(
    pos_id: int,
    payload: RealizeIn,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> RealizeResponse:
    """Record a partial or full sale of a CryptoPosition.

    Deducts quantity_sold from the source position, computes realized PL +
    estimated tax at the current holding period, and appends an immutable
    row to crypto_realizations. If the remaining quantity drops to zero we
    delete the position (a "closed" position with qty=0 clutters lists).
    """
    pos = session.get(CryptoPosition, pos_id)
    if pos is None or pos.user_id != user.id:
        raise HTTPException(404, "Crypto position not found")
    if payload.quantity_sold > pos.quantity + 1e-9:
        raise HTTPException(
            422,
            f"Can't sell {payload.quantity_sold} — you only hold {pos.quantity}.",
        )

    sold_at = payload.sold_at or datetime.utcnow()
    held_days = (sold_at - pos.created_at).days
    is_long_term = held_days >= _LONG_TERM_DAYS
    fed_rate = _FED_LT_RATE if is_long_term else _FED_ST_RATE
    combined = fed_rate + _STATE_RATE

    realized_pl = (payload.price_sold - pos.cost_basis_per_share) * payload.quantity_sold
    tax_owed_est = max(0.0, realized_pl) * combined  # never taxes losses

    r = CryptoRealization(
        position_id=pos_id,
        user_id=user.id or 0,
        quantity_sold=payload.quantity_sold,
        price_sold=payload.price_sold,
        cost_basis_per_share_at_sale=pos.cost_basis_per_share,
        realized_pl_usd=realized_pl,
        is_long_term=is_long_term,
        tax_owed_usd_est=tax_owed_est,
        sold_at=sold_at,
        note=(payload.note or "").strip() or None,
    )
    session.add(r)

    remaining = pos.quantity - payload.quantity_sold
    symbol = pos.symbol
    closed = remaining <= 1e-9
    if closed:
        session.delete(pos)
    else:
        pos.quantity = remaining
        pos.updated_at = datetime.utcnow()
        session.add(pos)

    session.commit()
    session.refresh(r)

    return RealizeResponse(
        realization=_realization_to_out(r, symbol),
        remaining_quantity=0.0 if closed else remaining,
        position_closed=closed,
    )


@router.get("/crypto/realizations", response_model=list[RealizationOut])
def list_crypto_realizations(
    limit: int = 100,
    user: User = Depends(require_pro),
    session: Session = Depends(get_session),
) -> list[RealizationOut]:
    """Full realized-PL ledger for the current user, newest first."""
    limit = max(1, min(limit, 500))
    rows = session.exec(
        select(CryptoRealization)
        .where(CryptoRealization.user_id == user.id)
        .order_by(CryptoRealization.sold_at.desc())
        .limit(limit)
    ).all()
    # Batch-resolve symbols for the position_ids referenced. Positions may
    # be deleted after being fully realized — fall back to '?' for those.
    if not rows:
        return []
    position_ids = list({r.position_id for r in rows})
    pos_rows = session.exec(
        select(CryptoPosition).where(CryptoPosition.id.in_(position_ids))
    ).all()
    sym_by_id = {p.id: p.symbol for p in pos_rows}
    return [_realization_to_out(r, sym_by_id.get(r.position_id, "?")) for r in rows]
