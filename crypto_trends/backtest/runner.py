"""Long/short top-N backtest with realistic frictions.

Convention: at each rebalance bar T, we observe data up to and including T
(the signal function is already non-look-ahead at row T), then trade at close[T]
and earn the close-to-close return from T to T+1. Operationally this is
implemented as `weights.shift(1) * returns`, so today's PnL uses yesterday's
weights — never the same-bar score, which would be lookahead.

All costs are charged on |Δweight| (turnover), in basis points. fee_bps covers
exchange commissions; slippage_bps covers the spread + market impact assumption.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

HOURS_PER_YEAR = 24 * 365      # crypto hourly bars
TRADING_DAYS_PER_YEAR = 252    # daily equity bars


@dataclass
class BacktestResult:
    equity: pd.Series           # cumulative P&L curve, starts at 1.0
    returns: pd.Series          # net per-bar returns
    weights: pd.DataFrame       # weights actually held into each bar
    metrics: dict[str, float]


def _select_top_n(scores_row: pd.Series, n: int) -> tuple[pd.Index, pd.Index]:
    """Pick the n highest and n lowest non-NaN scores. Returns (long_idx, short_idx)."""
    s = scores_row.dropna()
    if len(s) < 2 * n:
        # Not enough symbols to form non-overlapping legs.
        return pd.Index([]), pd.Index([])
    ranked = s.sort_values(ascending=False)
    longs = ranked.index[:n]
    shorts = ranked.index[-n:]
    return longs, shorts


def _scores_to_weights(scores: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Equal-weight, dollar-neutral: +1/n on top_n longs, -1/n on top_n shorts."""
    weights = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    w = 1.0 / top_n
    for ts, row in scores.iterrows():
        longs, shorts = _select_top_n(row, top_n)
        if len(longs) == 0:
            continue
        weights.loc[ts, longs] = w
        weights.loc[ts, shorts] = -w
    return weights


def run_backtest(
    close: pd.DataFrame,
    scores: pd.DataFrame,
    top_n: int = 5,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    rebalance_every: int = 1,
    bars_per_year: float = HOURS_PER_YEAR,
) -> BacktestResult:
    """Simulate a top-N long / bottom-N short, dollar-neutral, equal-weight portfolio.

    Args:
        close: wide DatetimeIndex × symbol close prices.
        scores: same shape as `close`. NaN cells are excluded from ranking.
        top_n: number of symbols per leg.
        fee_bps: exchange fee in bps, charged per side on turnover.
        slippage_bps: estimated execution slippage in bps, charged per side on turnover.

    Returns:
        BacktestResult with equity curve, per-bar returns, weights, and summary metrics.
    """
    if close.empty or scores.empty:
        empty = pd.Series(dtype=float)
        return BacktestResult(empty, empty, pd.DataFrame(), {})

    # Align scores to close. scores comes from non-look-ahead computation already.
    scores = scores.reindex_like(close)

    target_weights = _scores_to_weights(scores, top_n=top_n)
    if rebalance_every > 1:
        # Only act on every Nth bar; hold the previous target in between.
        mask = pd.Series(False, index=target_weights.index)
        mask.iloc[::rebalance_every] = True
        target_weights = target_weights.where(mask, np.nan).ffill().fillna(0.0)
    # Lag by one bar: today's PnL uses yesterday's chosen weights.
    held_weights = target_weights.shift(1).fillna(0.0)

    bar_returns = close.pct_change(fill_method=None)
    gross = (held_weights * bar_returns).sum(axis=1)

    # Turnover = sum of |Δweight| across symbols, charged each side.
    turnover = held_weights.diff().abs().sum(axis=1).fillna(held_weights.abs().sum(axis=1))
    cost_per_unit_turnover = (fee_bps + slippage_bps) / 1e4
    costs = turnover * cost_per_unit_turnover
    net = (gross - costs).fillna(0.0)

    equity = (1.0 + net).cumprod()

    metrics = _summary(net, turnover, bars_per_year=bars_per_year)
    return BacktestResult(equity=equity, returns=net, weights=held_weights, metrics=metrics)


def _summary(net_returns: pd.Series, turnover: pd.Series,
             bars_per_year: float = HOURS_PER_YEAR) -> dict[str, float]:
    r = net_returns.dropna()
    if len(r) < 2 or r.std() == 0:
        return {"sharpe": 0.0, "ann_return": 0.0, "max_drawdown": 0.0,
                "hit_rate": 0.0, "avg_turnover": 0.0, "n_bars": float(len(r))}

    sharpe = float(r.mean() / r.std() * np.sqrt(bars_per_year))
    ann_return = float((1 + r.mean()) ** bars_per_year - 1)

    equity = (1.0 + r).cumprod()
    running_max = equity.cummax()
    drawdown = (equity / running_max - 1.0).min()

    hit_rate = float((r > 0).mean())
    avg_turnover = float(turnover.dropna().mean())

    return {
        "sharpe": sharpe,
        "ann_return": ann_return,
        "max_drawdown": float(drawdown),
        "hit_rate": hit_rate,
        "avg_turnover": avg_turnover,
        "n_bars": float(len(r)),
    }


DEFAULTS = {
    # asset_class: (top_n, fee_bps, slippage_bps, rebalance_every, bars_per_year, lookback)
    "crypto":        (5, 10.0,   5.0, 24,   HOURS_PER_YEAR,        24),
    "crypto_micro":  (5, 10.0,  60.0, 24,   HOURS_PER_YEAR,        24),
    "equity_large":  (5,  5.0,  10.0,  5,   TRADING_DAYS_PER_YEAR,  5),
    "equity_micro":  (3,  5.0,  75.0, 10,   TRADING_DAYS_PER_YEAR,  5),
}


def main() -> None:
    """CLI: backtest momentum_v1 on the chosen asset class."""
    import argparse

    from crypto_trends.signals import momentum
    from crypto_trends.signals.loader import load_close_panel

    p = argparse.ArgumentParser(description="Backtest the momentum signal.")
    p.add_argument("--asset-class", default="crypto",
                   choices=["crypto", "crypto_micro", "equity_large", "equity_micro"])
    p.add_argument("--top-n", type=int, default=None)
    p.add_argument("--fee-bps", type=float, default=None)
    p.add_argument("--slippage-bps", type=float, default=None)
    p.add_argument("--rebalance-every", type=int, default=None,
                   help="Rebalance every N bars. Defaults sensibly per asset class.")
    args = p.parse_args()

    d_top, d_fee, d_slip, d_reb, bpy, lookback = DEFAULTS[args.asset_class]
    top_n = args.top_n or d_top
    fee_bps = args.fee_bps if args.fee_bps is not None else d_fee
    slippage_bps = args.slippage_bps if args.slippage_bps is not None else d_slip
    rebalance_every = args.rebalance_every or d_reb

    close = load_close_panel(asset_class=args.asset_class)
    if close.empty:
        print(f"No {args.asset_class} price data. Run ingestion first.")
        return

    scores = momentum.compute(close, lookback_hours=lookback)
    result = run_backtest(
        close=close, scores=scores, top_n=top_n,
        fee_bps=fee_bps, slippage_bps=slippage_bps,
        rebalance_every=rebalance_every, bars_per_year=bpy,
    )

    m = result.metrics
    print(f"Asset class:    {args.asset_class}")
    print(f"Bars:           {int(m['n_bars'])}")
    print(f"Top-N:          {top_n} long / {top_n} short")
    print(f"Costs:          {fee_bps} bps fee + {slippage_bps} bps slippage = "
          f"{fee_bps + slippage_bps} bps/side")
    print(f"Rebalance:      every {rebalance_every} bars")
    print(f"Sharpe (ann):   {m['sharpe']:.2f}")
    print(f"Ann. return:    {m['ann_return']*100:.1f}%")
    print(f"Max drawdown:   {m['max_drawdown']*100:.1f}%")
    print(f"Hit rate:       {m['hit_rate']*100:.1f}%")
    print(f"Avg turnover:   {m['avg_turnover']:.2f}  ({m['avg_turnover']*100:.0f}% of book/bar)")
    print(f"Final equity:   {result.equity.iloc[-1]:.4f}")


if __name__ == "__main__":
    main()
