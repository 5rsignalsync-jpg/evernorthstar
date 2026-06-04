"""Walk-forward parameter search for the momentum signal.

The naive single-pass backtest in `runner.py` fits parameters in-sample on the
entire history — the result is the textbook lookahead-flavored "looks great
until live trading". This module splits the history into train/test windows
that slide forward in time:

  [—— train ——][- test -][—— train ——][- test -] ...

For each window, we optimize the signal's params (lookback / RSI period /
weight blend) on the train slice's Sharpe, then evaluate the *frozen* params on
the next, never-seen test slice. The aggregated test-slice metric is what a
live strategy would have actually earned — no peeking.

Parameter grid is intentionally small. Larger grids look better in-sample but
overfit harder. The point of walk-forward is to surface that, not hide it.
"""

from __future__ import annotations

import argparse
import itertools
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from crypto_trends.backtest.runner import (
    DEFAULTS, HOURS_PER_YEAR, TRADING_DAYS_PER_YEAR, run_backtest,
)
from crypto_trends.signals import momentum
from crypto_trends.signals.loader import load_close_panel

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Params:
    lookback: int
    rsi_period: int
    return_weight: float
    rsi_weight: float


@dataclass
class WindowResult:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    best_train: Params
    train_sharpe: float
    test_sharpe: float
    test_return: float
    test_max_dd: float


def _build_grid(asset_class: str) -> list[Params]:
    """Compact grid — bigger grids invite overfitting on small histories."""
    if asset_class == "crypto":
        lookbacks = [12, 24, 48]
    else:
        lookbacks = [3, 5, 10]
    rsis = [7, 14, 21]
    blends = [(0.7, 0.3), (0.5, 0.5), (0.3, 0.7)]
    return [
        Params(lb, rsi, rw, sw)
        for lb in lookbacks for rsi in rsis for (rw, sw) in blends
    ]


def _score_slice(close: pd.DataFrame, p: Params, asset_class: str) -> tuple[float, float, float]:
    """Return (sharpe, ann_return, max_dd) for a slice with the given params."""
    if len(close) < max(p.lookback, p.rsi_period) + 5:
        return (np.nan, np.nan, np.nan)
    d_top, d_fee, d_slip, d_reb, bpy, _ = DEFAULTS[asset_class]
    scores = momentum.compute(
        close, lookback_hours=p.lookback, rsi_period=p.rsi_period,
        return_weight=p.return_weight, rsi_weight=p.rsi_weight,
    )
    result = run_backtest(
        close=close, scores=scores, top_n=d_top,
        fee_bps=d_fee, slippage_bps=d_slip,
        rebalance_every=d_reb, bars_per_year=bpy,
    )
    m = result.metrics
    return float(m["sharpe"]), float(m["ann_return"]), float(m["max_drawdown"])


def run_walk_forward(
    asset_class: str,
    train_bars: int | None = None,
    test_bars: int | None = None,
) -> list[WindowResult]:
    close = load_close_panel(asset_class=asset_class)
    if close.empty:
        log.warning("no price data for %s", asset_class)
        return []

    # Sensible defaults per asset class given typical histories.
    if train_bars is None:
        train_bars = 90 if asset_class == "crypto" else 120
    if test_bars is None:
        test_bars = 30 if asset_class == "crypto" else 30

    grid = _build_grid(asset_class)
    log.info("walk-forward on %s: %d bars total, train=%d, test=%d, grid=%d combos",
             asset_class, len(close), train_bars, test_bars, len(grid))

    results: list[WindowResult] = []
    start = 0
    while start + train_bars + test_bars <= len(close):
        train = close.iloc[start : start + train_bars]
        test = close.iloc[start + train_bars : start + train_bars + test_bars]

        best_params, best_sharpe = None, -np.inf
        for p in grid:
            sharpe, _, _ = _score_slice(train, p, asset_class)
            if not np.isnan(sharpe) and sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = p
        if best_params is None:
            start += test_bars
            continue

        # Need the lookback context for the test slice — slice from train_end - lookback.
        test_with_context = close.iloc[
            start + train_bars - max(best_params.lookback, best_params.rsi_period) :
            start + train_bars + test_bars
        ]
        sharpe, ann_ret, max_dd = _score_slice(test_with_context, best_params, asset_class)
        results.append(WindowResult(
            train_start=train.index[0], train_end=train.index[-1],
            test_start=test.index[0], test_end=test.index[-1],
            best_train=best_params,
            train_sharpe=best_sharpe,
            test_sharpe=sharpe, test_return=ann_ret, test_max_dd=max_dd,
        ))
        start += test_bars

    return results


def summarize(results: list[WindowResult]) -> dict[str, float]:
    if not results:
        return {}
    train_sharpes = np.array([r.train_sharpe for r in results])
    test_sharpes = np.array([r.test_sharpe for r in results if not np.isnan(r.test_sharpe)])
    return {
        "n_windows": float(len(results)),
        "mean_train_sharpe": float(np.nanmean(train_sharpes)),
        "mean_test_sharpe": float(np.nanmean(test_sharpes)) if len(test_sharpes) else float("nan"),
        "median_test_sharpe": float(np.nanmedian(test_sharpes)) if len(test_sharpes) else float("nan"),
        "train_minus_test": float(np.nanmean(train_sharpes) - np.nanmean(test_sharpes))
            if len(test_sharpes) else float("nan"),
    }


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="Walk-forward momentum parameter search.")
    p.add_argument("--asset-class", default="equity_large",
                   choices=["crypto", "equity_large", "equity_micro"])
    p.add_argument("--train-bars", type=int, default=None)
    p.add_argument("--test-bars", type=int, default=None)
    args = p.parse_args()

    results = run_walk_forward(args.asset_class, args.train_bars, args.test_bars)
    if not results:
        print("No windows — insufficient history.")
        return

    print(f"\n{'window':<6}{'train_start':<13}{'test_end':<13}{'lookback':>10}"
          f"{'rsi':>6}{'rw/sw':>10}{'train_sh':>10}{'test_sh':>10}{'test_ret':>10}")
    for i, r in enumerate(results, 1):
        bp = r.best_train
        print(f"{i:<6}{r.train_start.date()!s:<13}{r.test_end.date()!s:<13}"
              f"{bp.lookback:>10}{bp.rsi_period:>6}"
              f"{bp.return_weight:>5.1f}/{bp.rsi_weight:<4.1f}"
              f"{r.train_sharpe:>10.2f}{r.test_sharpe:>10.2f}{r.test_return*100:>9.1f}%")

    s = summarize(results)
    print()
    print(f"Windows:            {int(s['n_windows'])}")
    print(f"Mean train Sharpe:  {s['mean_train_sharpe']:.2f}")
    print(f"Mean test Sharpe:   {s['mean_test_sharpe']:.2f}")
    print(f"Median test Sharpe: {s['median_test_sharpe']:.2f}")
    print(f"Train − test gap:   {s['train_minus_test']:+.2f}  "
          f"(high gap = overfitting on grid)")


if __name__ == "__main__":
    main()
