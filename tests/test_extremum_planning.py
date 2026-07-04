"""Tests for the Sprint 1 + 2 planning engine.

Covers:
  - zone classification correctness on synthetic uptrends, downtrends, chops
  - Bollinger band position math
  - ring-fence scenario math and edge cases (no gain, no cost basis, etc.)
  - historical-outcome lookup (integration — needs seeded DuckDB)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from crypto_trends.data.store import connect
from crypto_trends.portfolio import planning
from crypto_trends.signals import extremum


# ---------------- Zone classification ----------------

def _synthetic(trend: str, n: int = 100, seed: int = 42) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2026-01-01", periods=n, freq="D")
    if trend == "uptrend_topped":
        base = np.linspace(100, 200, n) + rng.normal(0, 3, n)
        base[-10:] = base[-11] + np.linspace(0, 25, 10)   # sharp final surge
    elif trend == "downtrend_bottomed":
        base = np.linspace(200, 100, n) + rng.normal(0, 3, n)
        base[-10:] = base[-11] - np.linspace(0, 25, 10)   # sharp final drop
    elif trend == "sideways":
        base = 150 + rng.normal(0, 5, n)
    else:
        raise ValueError(trend)
    close = pd.Series(base, index=ts)
    vol = pd.Series(rng.integers(1_000_000, 5_000_000, n), index=ts, dtype=float)
    return close, vol


def test_topped_uptrend_classifies_as_distribution():
    close, vol = _synthetic("uptrend_topped")
    r = extremum.compute_zone(close, vol)
    assert r.zone in ("distribution", "extreme_distribution")
    assert r.zone_confidence > 0.3
    assert r.rsi is not None and r.rsi > 60
    assert r.bb_position_sigma is not None and r.bb_position_sigma > 0.5


def test_bottomed_downtrend_classifies_as_accumulation():
    close, vol = _synthetic("downtrend_bottomed")
    r = extremum.compute_zone(close, vol)
    assert r.zone == "accumulation"
    assert r.rsi is not None and r.rsi < 40
    assert r.bb_position_sigma is not None and r.bb_position_sigma < -0.5


def test_sideways_classifies_as_neutral():
    close, vol = _synthetic("sideways")
    r = extremum.compute_zone(close, vol)
    assert r.zone == "neutral"
    assert r.zone_confidence < 0.3


def test_zone_bounds_bracket_current_price():
    close, vol = _synthetic("uptrend_topped")
    r = extremum.compute_zone(close, vol)
    # The distribution zone should sit ABOVE the accumulation zone
    assert r.distribution_low is not None and r.accumulation_high is not None
    assert r.distribution_low > r.accumulation_high


def test_empty_series_returns_neutral():
    r = extremum.compute_zone(pd.Series(dtype=float))
    assert r.zone == "neutral"
    assert r.zone_confidence == 0.0
    assert r.current_price is None


def test_thin_history_degrades_gracefully():
    ts = pd.date_range("2026-01-01", periods=5, freq="D")
    close = pd.Series([100, 101, 102, 103, 104], index=ts, dtype=float)
    r = extremum.compute_zone(close)
    # 5 bars isn't enough for RSI(14) or BB(20) — should be neutral, no crash
    assert r.zone == "neutral"
    assert r.rsi is None
    assert r.bb_position_sigma is None
    assert r.current_price == 104.0


# ---------------- Ring-fence scenarios ----------------

def test_ring_fence_at_100pct_gain():
    # Bought 1 unit at $100, now $200 = 100% gain
    s = planning.compute_ring_fence_scenarios(
        quantity=1.0, current_price=200.0, cost_basis_per_share=100.0
    )
    assert len(s) == 3
    assert s[0].pct_of_gain_locked == 0.25
    assert s[0].amount_to_take_usd == pytest.approx(25)
    assert s[0].remaining_position_value == pytest.approx(175)
    # Take $25 - cost $100 = -$75 net if rest goes to zero
    assert s[0].net_pl_if_remainder_zero_usd == pytest.approx(-75)

    # Lock 50% → take $50, remainder $150
    assert s[1].amount_to_take_usd == pytest.approx(50)
    # $50 - $100 = -$50
    assert s[1].net_pl_if_remainder_zero_usd == pytest.approx(-50)


def test_ring_fence_no_gain_returns_empty():
    # Position is at cost basis, no gain to ring-fence
    s = planning.compute_ring_fence_scenarios(
        quantity=1.0, current_price=100.0, cost_basis_per_share=100.0
    )
    assert s == []


def test_ring_fence_underwater_returns_empty():
    # Position is at a loss
    s = planning.compute_ring_fence_scenarios(
        quantity=1.0, current_price=80.0, cost_basis_per_share=100.0
    )
    assert s == []


def test_ring_fence_invalid_inputs_return_empty():
    assert planning.compute_ring_fence_scenarios(0, 100, 50) == []
    assert planning.compute_ring_fence_scenarios(1, 0, 50) == []
    assert planning.compute_ring_fence_scenarios(1, 100, 0) == []


def test_ring_fence_5x_gain_scenario():
    """5x gain: lock 75% → $300 taken, $100 remaining position, +$200 net if rest zeros."""
    s = planning.compute_ring_fence_scenarios(
        quantity=1.0, current_price=500.0, cost_basis_per_share=100.0
    )
    lock_75 = s[2]
    assert lock_75.pct_of_gain_locked == 0.75
    assert lock_75.amount_to_take_usd == pytest.approx(300)
    assert lock_75.remaining_position_value == pytest.approx(200)
    assert lock_75.net_pl_if_remainder_zero_usd == pytest.approx(200)  # +$200 locked


# ---------------- Integration: build_position_plan ----------------

def test_build_position_plan_no_history_returns_none(tmp_db):
    plan = planning.build_position_plan(
        symbol="UNKNOWNCOIN", base="UNKNOWNCOIN", asset_class="crypto",
        quantity=1.0, cost_basis_per_share=100.0,
    )
    assert plan is None


def test_build_position_plan_with_history(tmp_db):
    # Seed enough OHLCV history for BTC
    base_ts = datetime(2026, 1, 1)
    with connect() as c:
        for i in range(120):
            ts = base_ts + timedelta(days=i)
            # Uptrend from 30k → 65k with some noise
            price = 30000 + i * 300 + (i * 37) % 500
            c.execute(
                "INSERT INTO ohlcv (symbol, ts, interval, source, open, high, low, close, volume) "
                "VALUES (?, ?, '1d', 'test', ?, ?, ?, ?, ?)",
                ["BTC", ts, price, price * 1.02, price * 0.98, price, 1_000_000],
            )
    plan = planning.build_position_plan(
        symbol="BTC", base="BTC", asset_class="crypto",
        quantity=0.5, cost_basis_per_share=32000.0,
    )
    assert plan is not None
    assert plan.symbol == "BTC"
    assert plan.quantity == 0.5
    assert plan.current_price is not None
    assert plan.current_value is not None
    assert plan.unrealized_gain_usd is not None
    assert plan.zone.zone in extremum.ZONES
    # Ring-fence should populate because we're in a gain
    assert len(plan.ring_fence_scenarios) == 3
