"""Position planning — Merlin-style entry/exit + profit-taking framework.

Given a user's holding (quantity, cost basis) and the current market state
(price, zone reading), we produce a "planning card" that shows:

  - The current unrealized gain / loss
  - Ring-fence scenarios (25% / 50% / 75% of gains locked in)
  - Historical context: at similar setups (zone + score percentile), what
    happened to the price 30 / 90 days later?
  - The zone's current price bounds (accumulation / distribution)

Legal posture: this module returns DATA. The framing layer (UI copy,
email subject lines) is what maintains our publisher exemption. We never
produce a "sell" / "buy" recommendation string here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

import pandas as pd

from crypto_trends.data.store import connect
from crypto_trends.signals.extremum import ZoneReading, compute_zone


@dataclass
class RingFenceScenario:
    """One row of the profit-taking framework table.

    net_pl_if_remainder_zero_usd is the worst-case PL if the remaining
    position went to zero after the ring-fence: it's the cash taken minus
    the original total cost. A NEGATIVE number here means "even if you
    take this ring-fence, you'd still be net-down if the rest goes to
    zero." Useful risk-management framing.
    """

    pct_of_gain_locked: float          # 0.25, 0.50, 0.75
    amount_to_take_usd: float          # dollar amount to ring-fence
    remaining_position_value: float    # what stays in the trade
    net_pl_if_remainder_zero_usd: float


@dataclass
class HistoricalOutcome:
    """A single historical similar-setup observation."""

    ticker: str
    setup_date: str
    setup_price: float
    fwd_30d_return_pct: Optional[float]
    fwd_90d_return_pct: Optional[float]


@dataclass
class HistoricalStats:
    """Summary of forward returns at similar setups. NEVER used as a
    prediction — we return descriptive stats about the past only."""

    n_setups: int
    median_fwd_30d_return_pct: Optional[float]
    median_fwd_90d_return_pct: Optional[float]
    p25_fwd_30d_return_pct: Optional[float]
    p75_fwd_30d_return_pct: Optional[float]
    sample: list[HistoricalOutcome]


@dataclass
class EntryTranche:
    """One rung of the entry ladder — an accumulation-zone limit level.

    These are descriptive price levels, not orders. `pct_of_budget` is the
    share of a planned budget suggested for this rung; `amount_usd` and
    `quantity` are filled only when a budget is provided.
    """

    label: str                      # "starter" / "core" / "deep"
    price: float                    # target accumulation price level
    pct_of_budget: float            # 0.30 / 0.35 / 0.35
    amount_usd: Optional[float]     # budget * pct, if a budget was given
    quantity: Optional[float]       # amount_usd / price, if computable


@dataclass
class EntryPlan:
    """Structured accumulation-zone entry ladder for one symbol.

    `status` describes where current price sits vs. the accumulation band:
    "in_zone" (inside the band now), "above_zone" (wait for a pullback),
    "below_zone" (under the band floor), or "unknown". Data only — never a
    buy instruction.
    """

    status: str
    accumulation_low: float
    accumulation_high: float
    invalidation_level: float       # a defined level below the band floor
    tranches: list[EntryTranche]
    note: str


@dataclass
class PositionPlan:
    """Complete planning payload for one position."""

    symbol: str
    base: str
    asset_class: str
    quantity: float
    cost_basis_per_share: Optional[float]
    current_price: Optional[float]
    current_value: Optional[float]
    unrealized_gain_usd: Optional[float]
    unrealized_gain_pct: Optional[float]
    zone: ZoneReading
    ring_fence_scenarios: list[RingFenceScenario]
    historical: Optional[HistoricalStats]
    entry_plan: Optional[EntryPlan]


def compute_ring_fence_scenarios(
    quantity: float,
    current_price: float,
    cost_basis_per_share: float,
) -> list[RingFenceScenario]:
    """Return the 25% / 50% / 75% of-gains ring-fence table for a position."""
    if cost_basis_per_share <= 0 or current_price <= 0 or quantity <= 0:
        return []
    total_cost = cost_basis_per_share * quantity
    total_value = current_price * quantity
    unrealized_gain = total_value - total_cost
    if unrealized_gain <= 0:
        # No gain to ring-fence; return empty rather than negative scenarios
        return []
    scenarios: list[RingFenceScenario] = []
    for pct in (0.25, 0.50, 0.75):
        take = unrealized_gain * pct
        remaining = total_value - take
        # Worst-case net PL = cash-in-hand minus original cost.
        # Negative = you'd still be net-down if the rest went to zero.
        # Positive = you've locked in a profit even if the rest wipes.
        net_pl_if_zero = take - total_cost
        scenarios.append(RingFenceScenario(
            pct_of_gain_locked=pct,
            amount_to_take_usd=take,
            remaining_position_value=remaining,
            net_pl_if_remainder_zero_usd=net_pl_if_zero,
        ))
    return scenarios


# Default entry ladder: three rungs across the accumulation band, weighted
# slightly toward the lower (better-priced) rungs.
_ENTRY_LADDER: tuple[tuple[str, float], ...] = (
    ("starter", 0.30),
    ("core", 0.35),
    ("deep", 0.35),
)
_INVALIDATION_BUFFER = 0.10  # invalidation sits 10% below the accumulation floor


def compute_entry_plan(
    accumulation_low: Optional[float],
    accumulation_high: Optional[float],
    current_price: Optional[float],
    budget_usd: Optional[float] = None,
) -> Optional[EntryPlan]:
    """Build a 3-rung accumulation-zone entry ladder from the zone bounds.

    Rungs sit at the top / middle / bottom of the accumulation band
    (starter / core / deep). Returns None when the band is unavailable or
    degenerate. Descriptive data only — preserves the publisher exemption
    (no "buy" instruction, just accumulation-zone levels).
    """
    if (
        accumulation_low is None
        or accumulation_high is None
        or accumulation_low <= 0
        or accumulation_high <= accumulation_low
    ):
        return None

    lo = float(accumulation_low)
    hi = float(accumulation_high)
    mid = (lo + hi) / 2.0
    rung_prices = {"starter": hi, "core": mid, "deep": lo}

    tranches: list[EntryTranche] = []
    for label, pct in _ENTRY_LADDER:
        price = rung_prices[label]
        amount = budget_usd * pct if (budget_usd and budget_usd > 0) else None
        qty = (amount / price) if (amount is not None and price > 0) else None
        tranches.append(EntryTranche(
            label=label,
            price=price,
            pct_of_budget=pct,
            amount_usd=amount,
            quantity=qty,
        ))

    invalidation = lo * (1.0 - _INVALIDATION_BUFFER)

    if current_price is None:
        status = "unknown"
    elif current_price > hi:
        status = "above_zone"
    elif current_price < lo:
        status = "below_zone"
    else:
        status = "in_zone"

    note = (
        "Accumulation-zone ladder from the current zone read. These are patient "
        "limit levels, not at-market orders, and not investment advice."
    )
    return EntryPlan(
        status=status,
        accumulation_low=lo,
        accumulation_high=hi,
        invalidation_level=invalidation,
        tranches=tranches,
        note=note,
    )


def _load_price_and_score_history(
    symbol: str, base: str, days: int = 365
) -> tuple[pd.Series, Optional[pd.Series], Optional[pd.Series]]:
    """Load close prices, volumes, and momentum scores for one symbol."""
    with connect(read_only=True) as conn:
        rows = conn.execute(
            f"""
            SELECT ts, close, volume
            FROM ohlcv
            WHERE (symbol = ? OR symbol = ?)
              AND ts >= now() - INTERVAL '{int(days)} days'
            ORDER BY ts ASC
            """,
            [symbol, base],
        ).fetchall()
        score_rows = conn.execute(
            f"""
            SELECT ts, score
            FROM signal_scores
            WHERE (symbol = ? OR symbol = ?)
              AND signal_name = 'momentum_v1'
              AND ts >= now() - INTERVAL '{int(days)} days'
            ORDER BY ts ASC
            """,
            [symbol, base],
        ).fetchall()
    if not rows:
        return pd.Series(dtype=float), None, None
    ts = pd.DatetimeIndex([r[0] for r in rows])
    close = pd.Series([float(r[1]) for r in rows], index=ts, name="close")
    volume = None
    if all(r[2] is not None for r in rows):
        volume = pd.Series([float(r[2]) for r in rows], index=ts, name="volume")
    scores: Optional[pd.Series] = None
    if score_rows:
        score_ts = pd.DatetimeIndex([r[0] for r in score_rows])
        scores = pd.Series(
            [float(r[1]) for r in score_rows], index=score_ts, name="score"
        )
    return close, volume, scores


def _lookup_historical_outcomes(
    symbol: str, base: str, zone: str, limit: int = 12
) -> HistoricalStats:
    """Find prior bars in this symbol's history where the zone was the
    same as it is now, then measure forward 30d / 90d returns from those
    setups.

    This is descriptive statistics on the PAST — we surface medians and
    quartiles so the user sees the distribution, not a point prediction.
    """
    close, volume, scores = _load_price_and_score_history(
        symbol, base, days=730  # 2 years for a bigger historical sample
    )
    if close.empty or len(close) < 60:
        return HistoricalStats(
            n_setups=0, median_fwd_30d_return_pct=None,
            median_fwd_90d_return_pct=None,
            p25_fwd_30d_return_pct=None, p75_fwd_30d_return_pct=None, sample=[]
        )

    # Walk historical bars, compute zone at each, collect matches
    matches: list[HistoricalOutcome] = []
    fwd_30d: list[float] = []
    fwd_90d: list[float] = []

    # Sample every 5th bar to keep this fast; we don't need every bar
    step = max(1, len(close) // 200)
    for i in range(60, len(close) - 90, step):
        window_close = close.iloc[: i + 1]
        window_vol = volume.iloc[: i + 1] if volume is not None else None
        window_scores = (
            scores[scores.index <= close.index[i]] if scores is not None else None
        )
        reading = compute_zone(window_close, window_vol, window_scores)
        if reading.zone != zone:
            continue
        setup_price = float(close.iloc[i])
        # Forward returns from this bar
        if i + 30 < len(close):
            fwd_30_price = float(close.iloc[i + 30])
            fwd_30d_return = (fwd_30_price / setup_price - 1) * 100
            fwd_30d.append(fwd_30d_return)
        else:
            fwd_30d_return = None
        if i + 90 < len(close):
            fwd_90_price = float(close.iloc[i + 90])
            fwd_90d_return = (fwd_90_price / setup_price - 1) * 100
            fwd_90d.append(fwd_90d_return)
        else:
            fwd_90d_return = None

        matches.append(HistoricalOutcome(
            ticker=base,
            setup_date=str(close.index[i].date()),
            setup_price=setup_price,
            fwd_30d_return_pct=fwd_30d_return,
            fwd_90d_return_pct=fwd_90d_return,
        ))

    median_30 = float(pd.Series(fwd_30d).median()) if fwd_30d else None
    median_90 = float(pd.Series(fwd_90d).median()) if fwd_90d else None
    p25_30 = float(pd.Series(fwd_30d).quantile(0.25)) if fwd_30d else None
    p75_30 = float(pd.Series(fwd_30d).quantile(0.75)) if fwd_30d else None

    # Return the most recent `limit` matches as the sample
    sample = sorted(matches, key=lambda m: m.setup_date, reverse=True)[:limit]

    return HistoricalStats(
        n_setups=len(matches),
        median_fwd_30d_return_pct=median_30,
        median_fwd_90d_return_pct=median_90,
        p25_fwd_30d_return_pct=p25_30,
        p75_fwd_30d_return_pct=p75_30,
        sample=sample,
    )


def build_position_plan(
    symbol: str,
    base: str,
    asset_class: str,
    quantity: float,
    cost_basis_per_share: Optional[float] = None,
) -> Optional[PositionPlan]:
    """Build the full planning payload for one position.

    Returns None only if there's zero price history for the symbol.
    Everything else degrades gracefully to None fields.
    """
    close, volume, scores = _load_price_and_score_history(symbol, base, days=365)
    if close.empty:
        return None

    zone_reading = compute_zone(close, volume, scores)
    current_price = zone_reading.current_price

    current_value = None
    unrealized_gain_usd = None
    unrealized_gain_pct = None
    if current_price is not None and quantity is not None:
        current_value = current_price * quantity

    ring_fence: list[RingFenceScenario] = []
    if (
        current_price is not None
        and cost_basis_per_share is not None
        and cost_basis_per_share > 0
        and quantity > 0
    ):
        total_cost = cost_basis_per_share * quantity
        assert current_value is not None
        unrealized_gain_usd = current_value - total_cost
        unrealized_gain_pct = (
            (current_price / cost_basis_per_share - 1) * 100 if cost_basis_per_share else None
        )
        ring_fence = compute_ring_fence_scenarios(
            quantity=quantity,
            current_price=current_price,
            cost_basis_per_share=cost_basis_per_share,
        )

    historical: Optional[HistoricalStats] = None
    # Only lookup historical outcomes for non-neutral zones — neutral is the
    # default and doesn't have interesting forward-return distributions
    if zone_reading.zone != "neutral":
        historical = _lookup_historical_outcomes(symbol, base, zone_reading.zone)

    entry_plan = compute_entry_plan(
        accumulation_low=zone_reading.accumulation_low,
        accumulation_high=zone_reading.accumulation_high,
        current_price=current_price,
    )

    return PositionPlan(
        symbol=symbol,
        base=base,
        asset_class=asset_class,
        quantity=quantity,
        cost_basis_per_share=cost_basis_per_share,
        current_price=current_price,
        current_value=current_value,
        unrealized_gain_usd=unrealized_gain_usd,
        unrealized_gain_pct=unrealized_gain_pct,
        zone=zone_reading,
        ring_fence_scenarios=ring_fence,
        historical=historical,
        entry_plan=entry_plan,
    )
