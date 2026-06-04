"""Long-term buy/hold signal: quality + value + momentum blend.

Score is in roughly [-1, 1] but the intended use is *long-only*: take the
highest-scoring names and hold equal-weight, rebalanced monthly. Top-quintile
picks are what the dashboard surfaces.

Components (each z-scored across the cross-section, then tanh-squashed):
  Quality  = avg(zscore(ROE), -zscore(debt_to_equity), zscore(profit_margin))
  Value    = avg(-zscore(PE), -zscore(P/B))     [low PE/PB → positive score]
  Momentum = zscore of 12-1 return (12-month return excluding the most recent month)

Blend defaults: quality 0.35, value 0.25, momentum 0.40.
Missing components fall back to zero (neutral) for that component, with the
remaining weights re-normalized.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SIGNAL_NAME = "long_term_v1"

_MOM_WINDOW = 252            # ~1 year of trading days
_MOM_SKIP = 21               # ~1 month skip


def _zscore(s: pd.Series) -> pd.Series:
    mu, sd = s.mean(), s.std()
    if sd == 0 or pd.isna(sd):
        return pd.Series(0.0, index=s.index)
    return (s - mu) / sd


def _safe_tanh(s: pd.Series) -> pd.Series:
    return s.apply(lambda x: float(np.tanh(x / 2.0)) if pd.notna(x) else np.nan)


def compute_components(
    close: pd.DataFrame,
    fundamentals: pd.DataFrame,
) -> pd.DataFrame:
    """Return a per-symbol DataFrame with columns [quality, value, momentum].

    Args:
        close: wide DatetimeIndex × symbol daily closes.
        fundamentals: DataFrame indexed by symbol with columns
            roe, debt_to_equity, profit_margin, pe, pb.
    """
    symbols = [s for s in close.columns if s in fundamentals.index]
    if not symbols:
        return pd.DataFrame(columns=["quality", "value", "momentum"])
    f = fundamentals.loc[symbols]

    # Quality
    roe_z = _zscore(f["roe"])
    de_z = -_zscore(f["debt_to_equity"])     # lower debt is better
    pm_z = _zscore(f["profit_margin"])
    quality = pd.concat([roe_z, de_z, pm_z], axis=1).mean(axis=1)

    # Value
    pe_z = -_zscore(f["pe"])                 # lower PE is better
    pb_z = -_zscore(f["pb"])
    value = pd.concat([pe_z, pb_z], axis=1).mean(axis=1)

    # 12-1 momentum on price
    sub = close[symbols].dropna(how="all")
    if len(sub) < _MOM_WINDOW + _MOM_SKIP:
        mom = pd.Series(np.nan, index=symbols)
    else:
        end_price = sub.iloc[-_MOM_SKIP - 1]
        start_price = sub.iloc[-_MOM_WINDOW - _MOM_SKIP - 1] \
            if len(sub) >= _MOM_WINDOW + _MOM_SKIP + 1 else sub.iloc[0]
        ret = (end_price / start_price) - 1.0
        mom = _zscore(ret)

    return pd.DataFrame({
        "quality": _safe_tanh(quality),
        "value": _safe_tanh(value),
        "momentum": _safe_tanh(mom.reindex(symbols)),
    })


def compute(
    close: pd.DataFrame,
    fundamentals: pd.DataFrame,
    weights: dict[str, float] | None = None,
) -> pd.Series:
    """Compute the blended long-term score per symbol.

    Returns: Series indexed by symbol, score in roughly [-1, 1].
    """
    if weights is None:
        weights = {"quality": 0.35, "value": 0.25, "momentum": 0.40}

    comps = compute_components(close, fundamentals)
    if comps.empty:
        return pd.Series(dtype=float)

    # Re-normalize weights for whichever components are present per-symbol.
    score = pd.Series(0.0, index=comps.index)
    total = pd.Series(0.0, index=comps.index)
    for k, w in weights.items():
        valid = comps[k].notna()
        score = score + comps[k].fillna(0.0) * w * valid.astype(float)
        total = total + w * valid.astype(float)
    score = score / total.replace(0.0, np.nan)
    return score
