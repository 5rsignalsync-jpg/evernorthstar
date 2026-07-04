"""Extremum detection + entry/exit zone computation for the crypto sleeve.

This is the engine behind the "Merlin-style" position planning UI. Given
a symbol's price history, we produce:

  - A zone classification: accumulation / neutral / distribution / extreme
  - Numeric zone boundaries in price terms (accumulation_low..high,
    distribution_low..high) so the frontend can render bands on a chart
  - Component readings (RSI, Bollinger band position σ, score percentile,
    volume divergence flag) so we can be transparent about WHY a zone
    was assigned

Pure function — no I/O, no globals, deterministic given input. Legal
posture: we describe zones descriptively ("distribution zone"), never
prescriptively ("sell here"). The UI + copy layer is responsible for
maintaining that framing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


ZONES = ("accumulation", "neutral", "distribution", "extreme_distribution")


@dataclass
class ZoneReading:
    """Snapshot for the most recent bar of a symbol's history."""

    zone: str                        # one of ZONES
    zone_confidence: float           # 0..1 — how strong the signals agree
    rsi: Optional[float]             # 14-period Wilder RSI
    bb_position_sigma: Optional[float]  # sigma above/below the 20-day MA
    score_percentile: Optional[float]   # our momentum_v1 score, 0..1 of 90d dist
    volume_divergence: bool          # True when price↑ but volume↓ or vice-versa
    accumulation_low: Optional[float]
    accumulation_high: Optional[float]
    distribution_low: Optional[float]
    distribution_high: Optional[float]
    current_price: Optional[float]


def _wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.where(avg_loss > 0)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    no_loss = (avg_loss == 0) & avg_gain.notna()
    rsi = rsi.mask(no_loss & (avg_gain > 0), 100.0)
    rsi = rsi.mask(no_loss & (avg_gain == 0), 50.0)
    return rsi


def _bollinger_position_sigma(close: pd.Series, window: int = 20) -> pd.Series:
    """Signed distance from the SMA in units of std dev. +2 means at the upper
    band; -2 at the lower band; 0 at the mean. NaN before the window fills."""
    sma = close.rolling(window=window, min_periods=window).mean()
    std = close.rolling(window=window, min_periods=window).std()
    with np.errstate(divide="ignore", invalid="ignore"):
        return (close - sma) / std.where(std > 0)


def _score_percentile(scores: pd.Series, window: int = 90) -> pd.Series:
    """Rolling percentile rank of the latest score within the last `window`
    scores. 0.5 = median of the window. Requires at least window/2 non-null
    values to emit a reading."""

    def _pct(x: np.ndarray) -> float:
        finite = x[np.isfinite(x)]
        if len(finite) < max(5, window // 4):
            return float("nan")
        current = x[-1]
        if not np.isfinite(current):
            return float("nan")
        return float((finite <= current).sum() / len(finite))

    return scores.rolling(window=window, min_periods=window // 2).apply(
        _pct, raw=True
    )


def _volume_divergence(close: pd.Series, volume: pd.Series, window: int = 20) -> bool:
    """Detect divergence: price making higher highs while volume declines,
    or vice-versa. This is a classic distribution signal at tops. Only
    considers the most recent bar."""
    if len(close) < window + 5 or len(volume) < window + 5:
        return False
    recent_price = close.iloc[-window:]
    recent_volume = volume.iloc[-window:]
    if recent_price.isna().any() or recent_volume.isna().any():
        return False
    # Price trend: slope of a simple linear fit
    x = np.arange(window, dtype=float)
    price_slope = np.polyfit(x, recent_price.values, 1)[0]
    volume_slope = np.polyfit(x, recent_volume.values, 1)[0]
    price_std = float(recent_price.std())
    vol_std = float(recent_volume.std())
    if price_std == 0 or vol_std == 0:
        return False
    # Normalize both slopes then check opposite signs with enough magnitude
    price_norm = price_slope / (price_std / window)
    volume_norm = volume_slope / (vol_std / window)
    return price_norm * volume_norm < -0.5


def _classify_zone(
    rsi: Optional[float],
    bb_sigma: Optional[float],
    score_pct: Optional[float],
    volume_div: bool,
) -> tuple[str, float]:
    """Combine the four component signals into a zone + confidence.

    Convention: each signal produces a per-component score in [-1, 1] where
    -1 means strongly at the bottom, +1 strongly at the top. We take the mean
    of the non-null components as the composite. Volume divergence adds a
    'push toward extreme' when the direction is already indicated.

    Bounds:
      composite ≥  0.7  → extreme_distribution
      composite ∈ [0.3, 0.7)  → distribution
      composite ∈ (-0.3, 0.3) → neutral
      composite ≤ -0.3  → accumulation

    Confidence = |composite| ∈ [0, 1].
    """
    components: list[float] = []
    if rsi is not None:
        # RSI 30-70 is neutral; map RSI 0-100 to component -1..+1 centered at 50
        components.append((rsi - 50.0) / 50.0)
    if bb_sigma is not None:
        # +2σ ≈ 1.0, -2σ ≈ -1.0. Beyond that, clip.
        components.append(float(np.clip(bb_sigma / 2.0, -1.0, 1.0)))
    if score_pct is not None:
        # 50th %ile → 0, 100th → +1, 0th → -1
        components.append((score_pct - 0.5) * 2.0)

    if not components:
        return "neutral", 0.0

    composite = float(np.mean(components))
    # Volume divergence pushes toward the current side with a small boost
    if volume_div and abs(composite) > 0.1:
        composite = float(np.clip(composite * 1.15, -1.0, 1.0))

    if composite >= 0.7:
        return "extreme_distribution", abs(composite)
    if composite >= 0.3:
        return "distribution", abs(composite)
    if composite <= -0.3:
        return "accumulation", abs(composite)
    return "neutral", abs(composite)


def _compute_zone_bounds(
    close: pd.Series, bb_window: int = 20, k: float = 2.0
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Compute price-level bounds for the accumulation and distribution zones.
    Uses Bollinger bands as anchors and shades the extreme zones outside them.

    Returns (acc_low, acc_high, dist_low, dist_high). Any may be None if not
    enough history."""
    if len(close) < bb_window:
        return None, None, None, None
    sma = close.rolling(window=bb_window, min_periods=bb_window).mean()
    std = close.rolling(window=bb_window, min_periods=bb_window).std()
    sma_now = sma.iloc[-1]
    std_now = std.iloc[-1]
    if not (np.isfinite(sma_now) and np.isfinite(std_now) and std_now > 0):
        return None, None, None, None
    # Accumulation zone: 1σ..2σ below the mean
    acc_high = float(sma_now - std_now)
    acc_low = float(sma_now - k * std_now)
    # Distribution zone: 1σ..2σ above the mean
    dist_low = float(sma_now + std_now)
    dist_high = float(sma_now + k * std_now)
    return acc_low, acc_high, dist_low, dist_high


def compute_zone(
    close: pd.Series,
    volume: Optional[pd.Series] = None,
    score_history: Optional[pd.Series] = None,
    rsi_period: int = 14,
    bb_window: int = 20,
    score_percentile_window: int = 90,
) -> ZoneReading:
    """Given the price + volume + score history for ONE symbol, return the
    current-bar zone reading.

    Inputs:
      close:   pd.Series indexed by time, close prices.
      volume:  optional pd.Series indexed by time, trading volumes.
      score_history: optional pd.Series of our momentum_v1 scores, aligned
                     to `close`'s index (missing values OK).

    Returns:
      ZoneReading — never raises. When history is thin, components are
      None and zone is 'neutral' with confidence 0.
    """
    if close.empty:
        return ZoneReading(
            zone="neutral", zone_confidence=0.0, rsi=None, bb_position_sigma=None,
            score_percentile=None, volume_divergence=False,
            accumulation_low=None, accumulation_high=None,
            distribution_low=None, distribution_high=None,
            current_price=None,
        )

    close = close.dropna()
    current_price = float(close.iloc[-1]) if len(close) else None

    rsi_val: Optional[float] = None
    if len(close) >= rsi_period + 5:
        rsi_series = _wilder_rsi(close, period=rsi_period)
        v = rsi_series.iloc[-1]
        rsi_val = float(v) if np.isfinite(v) else None

    bb_val: Optional[float] = None
    if len(close) >= bb_window:
        bb_series = _bollinger_position_sigma(close, window=bb_window)
        v = bb_series.iloc[-1]
        bb_val = float(v) if np.isfinite(v) else None

    pct_val: Optional[float] = None
    if score_history is not None and len(score_history) >= 10:
        pct_series = _score_percentile(
            score_history.dropna(), window=score_percentile_window
        )
        if len(pct_series):
            v = pct_series.iloc[-1]
            pct_val = float(v) if np.isfinite(v) else None

    vol_div = False
    if volume is not None:
        vol_aligned = volume.reindex(close.index)
        vol_div = _volume_divergence(close, vol_aligned)

    zone, confidence = _classify_zone(rsi_val, bb_val, pct_val, vol_div)
    acc_low, acc_high, dist_low, dist_high = _compute_zone_bounds(
        close, bb_window=bb_window
    )

    return ZoneReading(
        zone=zone,
        zone_confidence=confidence,
        rsi=rsi_val,
        bb_position_sigma=bb_val,
        score_percentile=pct_val,
        volume_divergence=vol_div,
        accumulation_low=acc_low,
        accumulation_high=acc_high,
        distribution_low=dist_low,
        distribution_high=dist_high,
        current_price=current_price,
    )
