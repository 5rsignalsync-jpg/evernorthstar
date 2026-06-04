"""Momentum signal v1.

Cross-sectional momentum score: at each timestamp, ranks every symbol by a
blend of recent return and RSI, then squashes to roughly [-1, 1] via tanh.

Pure function — no I/O, no globals, deterministic given input.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SIGNAL_NAME = "momentum_v1"


def _rsi(close: pd.DataFrame, period: int) -> pd.DataFrame:
    """Wilder's RSI across each column. NaN until `period` bars have passed.

    Edge cases (after enough history):
      avg_loss == 0 and avg_gain >  0 → 100 (perfect uptrend)
      avg_loss == 0 and avg_gain == 0 → 50  (no movement)
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder smoothing == EMA with alpha=1/period
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.where(avg_loss > 0)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # Where avg_loss == 0: 100 if there were any gains, else 50.
    no_loss = (avg_loss == 0) & avg_gain.notna()
    rsi = rsi.mask(no_loss & (avg_gain > 0), 100.0)
    rsi = rsi.mask(no_loss & (avg_gain == 0), 50.0)
    return rsi


def compute(
    close: pd.DataFrame,
    lookback_hours: int = 24,
    rsi_period: int = 14,
    return_weight: float = 0.6,
    rsi_weight: float = 0.4,
) -> pd.DataFrame:
    """Compute momentum scores from a wide close-price DataFrame.

    Args:
        close: DatetimeIndex × symbol columns, chronological. Values are close prices.
        lookback_hours: Window for the return component.
        rsi_period: Period for RSI.
        return_weight: Weight on the return-z component.
        rsi_weight: Weight on the centered-RSI component.

    Returns:
        DataFrame with same shape as `close`. Each value is the symbol's score at that
        timestamp, in roughly [-1, 1]. Early rows (before enough history) are NaN.
    """
    if close.empty:
        return close.copy()

    # 1) Lookback return, cross-sectionally z-scored, then tanh-squashed.
    ret = close.pct_change(periods=lookback_hours, fill_method=None)
    # Cross-sectional z-score: per-row mean/std across symbols.
    row_mean = ret.mean(axis=1)
    row_std = ret.std(axis=1).replace(0.0, np.nan)
    ret_z = ret.sub(row_mean, axis=0).div(row_std, axis=0)
    ret_component = np.tanh(ret_z / 2.0)  # /2 keeps typical values away from saturation

    # 2) Centered RSI, tanh-squashed for symmetry with the return component.
    rsi = _rsi(close, period=rsi_period)
    rsi_component = np.tanh((rsi - 50.0) / 25.0)  # RSI=75 ≈ 0.76, RSI=25 ≈ -0.76

    # Weighted blend; if one component is missing for a cell, fall back to the other
    # so an entire symbol doesn't drop out for a single NaN.
    total_weight = return_weight + rsi_weight
    score = (return_weight * ret_component + rsi_weight * rsi_component) / total_weight
    only_ret = score.isna() & ret_component.notna()
    only_rsi = score.isna() & rsi_component.notna()
    score = score.mask(only_ret, ret_component)
    score = score.mask(only_rsi, rsi_component)
    return score


def components(
    close: pd.DataFrame,
    lookback_hours: int = 24,
    rsi_period: int = 14,
) -> dict[str, pd.DataFrame]:
    """Return the raw sub-components for debugging / transparency."""
    return {
        "return_pct": close.pct_change(periods=lookback_hours, fill_method=None),
        "rsi": _rsi(close, period=rsi_period),
    }
