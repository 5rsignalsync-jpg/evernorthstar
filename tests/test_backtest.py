"""Sanity tests for the backtest.

Verifies no-lookahead, dollar-neutral weights, and that costs reduce returns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_trends.backtest.runner import run_backtest


def _panel(n: int, paths: dict[str, np.ndarray]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="1h")
    return pd.DataFrame(paths, index=idx)


def test_weights_are_dollar_neutral():
    n = 100
    rng = np.random.default_rng(1)
    syms = [f"S{i}" for i in range(6)]
    close = _panel(n, {s: 100 * np.cumprod(1 + rng.normal(0, 0.01, n)) for s in syms})
    # Random scores
    scores = pd.DataFrame(rng.normal(0, 1, (n, 6)), index=close.index, columns=syms)

    res = run_backtest(close, scores, top_n=2, fee_bps=0, slippage_bps=0)

    # Each row that has any weight should sum to ~0 (dollar-neutral).
    row_sums = res.weights.sum(axis=1)
    nonzero_rows = res.weights.abs().sum(axis=1) > 0
    assert np.allclose(row_sums[nonzero_rows], 0.0, atol=1e-9)


def test_no_lookahead():
    """Scores at time T only affect PnL at time T+1 and later."""
    n = 50
    close = _panel(n, {
        "A": np.linspace(100, 200, n),  # constant +1% bars-ish
        "B": np.linspace(200, 100, n),
        "C": np.linspace(100, 150, n),
        "D": np.linspace(150, 100, n),
    })
    # Perfect-foresight scores: positive for risers, negative for fallers.
    scores = pd.DataFrame(
        {"A": 1.0, "B": -1.0, "C": 0.5, "D": -0.5},
        index=close.index,
    )

    res = run_backtest(close, scores, top_n=1, fee_bps=0, slippage_bps=0)

    # First bar's PnL must be 0 — held_weights = scores.shift(1) is NaN/0 for row 0.
    assert res.returns.iloc[0] == 0.0


def test_costs_reduce_returns():
    n = 100
    rng = np.random.default_rng(2)
    syms = [f"S{i}" for i in range(6)]
    close = _panel(n, {s: 100 * np.cumprod(1 + rng.normal(0, 0.01, n)) for s in syms})
    scores = pd.DataFrame(rng.normal(0, 1, (n, 6)), index=close.index, columns=syms)

    no_cost = run_backtest(close, scores, top_n=2, fee_bps=0, slippage_bps=0)
    with_cost = run_backtest(close, scores, top_n=2, fee_bps=10, slippage_bps=5)

    assert with_cost.equity.iloc[-1] < no_cost.equity.iloc[-1]
