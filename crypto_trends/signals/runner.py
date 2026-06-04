"""Compute signals and persist to DuckDB."""

from __future__ import annotations

import argparse
import json
import logging

import pandas as pd

from crypto_trends.data.store import connect
from crypto_trends.signals import long_term, momentum
from crypto_trends.signals.loader import load_close_panel

log = logging.getLogger(__name__)


def compute_and_store_momentum(
    asset_class: str = "crypto",
    latest_only: bool = True,
    lookback_hours: int | None = None,
    rsi_period: int = 14,
) -> int:
    close = load_close_panel(asset_class=asset_class)
    if close.empty:
        log.warning("no %s OHLCV loaded — run ingestion first", asset_class)
        return 0

    # Sensible default lookbacks per asset class. Equities trade daily; "24 hours"
    # there means 24 trading days (~1 month) which is too slow. Use 5 days (1 week).
    if lookback_hours is None:
        lookback_hours = 24 if asset_class.startswith("crypto") else 5

    scores = momentum.compute(close, lookback_hours=lookback_hours, rsi_period=rsi_period)
    comps = momentum.components(close, lookback_hours=lookback_hours, rsi_period=rsi_period)

    if latest_only:
        # Most recent timestamp where AT LEAST half the universe has a score —
        # tolerates newly-listed symbols with thin history that would otherwise
        # prevent any row from being "all valid".
        min_valid = max(2, len(scores.columns) // 2)
        valid_counts = scores.notna().sum(axis=1)
        eligible = scores.index[valid_counts >= min_valid]
        if len(eligible) == 0:
            log.warning("no row has a score for ≥half the universe yet (need more history)")
            return 0
        last_valid = eligible.max()
        scores = scores.loc[[last_valid]]
        comps = {k: v.loc[[last_valid]] for k, v in comps.items()}

    rows: list[tuple] = []
    for ts, row in scores.iterrows():
        for sym, score in row.items():
            if pd.isna(score):
                continue
            comp_payload = {
                k: (None if pd.isna(v.at[ts, sym]) else float(v.at[ts, sym]))
                for k, v in comps.items()
            }
            rows.append(
                (sym, ts.to_pydatetime(), momentum.SIGNAL_NAME, float(score),
                 json.dumps(comp_payload))
            )

    if not rows:
        return 0

    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO signal_scores (symbol, ts, signal_name, score, components, computed_at)
            VALUES (?, ?, ?, ?, ?, now())
            ON CONFLICT (symbol, ts, signal_name) DO UPDATE SET
                score = excluded.score,
                components = excluded.components,
                computed_at = now()
            """,
            rows,
        )
    return len(rows)


def compute_and_store_long_term(asset_class: str = "equity_large") -> int:
    """Compute the long-term buy/hold score for the most recent bar."""
    close = load_close_panel(asset_class=asset_class)
    if close.empty:
        log.warning("no %s prices loaded", asset_class)
        return 0

    with connect(read_only=True) as conn:
        f_df = conn.execute(
            """
            SELECT f.symbol, f.market_cap, f.pe, f.pb, f.roe,
                   f.debt_to_equity, f.profit_margin
            FROM fundamentals f
            JOIN universe u ON u.symbol = f.symbol
            WHERE u.asset_class = ?
              AND u.included
              AND f.as_of = (SELECT MAX(as_of) FROM fundamentals WHERE symbol = f.symbol)
            """,
            [asset_class],
        ).fetchdf()

    if f_df.empty:
        log.warning("no fundamentals for %s — run fundamentals ingestion first",
                    asset_class)
        return 0

    f_df = f_df.set_index("symbol")
    scores = long_term.compute(close, f_df).dropna()
    if scores.empty:
        return 0

    ts = close.index.max().to_pydatetime()
    rows = [(sym, ts, long_term.SIGNAL_NAME, float(score), json.dumps({}))
            for sym, score in scores.items()]

    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO signal_scores (symbol, ts, signal_name, score, components, computed_at)
            VALUES (?, ?, ?, ?, ?, now())
            ON CONFLICT (symbol, ts, signal_name) DO UPDATE SET
                score = excluded.score,
                computed_at = now()
            """,
            rows,
        )
    return len(rows)


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="Compute & store signal scores.")
    p.add_argument("--signal", default="momentum",
                   choices=["momentum", "long_term", "all"])
    p.add_argument("--asset-class", default="crypto",
                   choices=["crypto", "crypto_micro", "equity_large", "equity_micro", "all"])
    p.add_argument("--all-history", action="store_true",
                   help="Momentum only: compute scores for the full history (slower).")
    args = p.parse_args()

    classes = ["crypto", "crypto_micro", "equity_large", "equity_micro"] \
        if args.asset_class == "all" else [args.asset_class]

    total = 0
    if args.signal in ("momentum", "all"):
        for ac in classes:
            n = compute_and_store_momentum(asset_class=ac, latest_only=not args.all_history)
            print(f"  momentum / {ac}: wrote {n} rows")
            total += n
    if args.signal in ("long_term", "all"):
        # Long-term sleeve only makes sense for equities.
        for ac in [c for c in classes if c.startswith("equity_")]:
            n = compute_and_store_long_term(asset_class=ac)
            print(f"  long_term / {ac}: wrote {n} rows")
            total += n
    print(f"\nTotal: {total} signal_scores rows.")


if __name__ == "__main__":
    main()
