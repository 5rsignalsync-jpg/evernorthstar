"""Sanity tests for the momentum signal.

These don't test alpha — they verify the function's shape, sign, and
boundedness on synthetic inputs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_trends.signals import momentum


def _panel(n: int, paths: dict[str, np.ndarray]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="1h")
    return pd.DataFrame(paths, index=idx)


def test_uptrend_is_positive():
    n = 100
    up = np.linspace(100, 150, n)
    flat = np.full(n, 100.0)
    down = np.linspace(100, 70, n)
    close = _panel(n, {"UP": up, "FLAT": flat, "DOWN": down})

    scores = momentum.compute(close).iloc[-1]

    assert scores["UP"] > 0.3, scores
    assert scores["DOWN"] < -0.3, scores
    assert -0.3 < scores["FLAT"] < 0.3, scores


def test_scores_are_bounded():
    rng = np.random.default_rng(42)
    n = 500
    paths = {f"S{i}": 100 * np.cumprod(1 + rng.normal(0, 0.01, n)) for i in range(10)}
    close = _panel(n, paths)

    scores = momentum.compute(close).dropna(how="all")

    assert scores.values.min() >= -1.0001
    assert scores.values.max() <= 1.0001


def test_early_rows_before_any_component_valid_are_nan():
    n = 50
    close = _panel(n, {"A": np.linspace(100, 120, n), "B": np.linspace(120, 100, n)})

    scores = momentum.compute(close, lookback_hours=24, rsi_period=14)

    # Before rsi_period bars have passed, no component is valid yet.
    assert scores.iloc[:14].isna().all().all()
    # After both windows are warmed up, every cell has a value.
    assert scores.iloc[25:].notna().all().all()


def test_empty_input_returns_empty():
    out = momentum.compute(pd.DataFrame())
    assert out.empty
