"""Snapshot fundamentals via yfinance Ticker.info.

This is a *point-in-time* snapshot — yfinance only exposes the current view, not
historical fundamentals. For the long-term sleeve this is fine for *current*
recommendations, but it means we cannot honestly backtest the long-term factor
signal with historical fundamentals. Backtests of the long-term sleeve are
therefore price-momentum-only; the fundamental components only affect today's
ranking.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from typing import Any

import yfinance as yf

from crypto_trends.data.store import connect

log = logging.getLogger(__name__)


def _pick(info: dict[str, Any], *keys: str) -> float | None:
    """First non-null numeric value among the given keys."""
    for k in keys:
        v = info.get(k)
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f == f:  # NaN check
            return f
    return None


def fetch_one(symbol: str) -> dict[str, Any]:
    info = yf.Ticker(symbol).info or {}
    return {
        "market_cap": _pick(info, "marketCap"),
        "pe": _pick(info, "trailingPE"),
        "forward_pe": _pick(info, "forwardPE"),
        "pb": _pick(info, "priceToBook"),
        "roe": _pick(info, "returnOnEquity"),
        "debt_to_equity": _pick(info, "debtToEquity"),
        "profit_margin": _pick(info, "profitMargins"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }


def ingest_for_asset_class(asset_class: str) -> int:
    """Fetch fundamentals for all included symbols of the given asset class."""
    with connect(read_only=True) as conn:
        tickers = [
            r[0] for r in conn.execute(
                "SELECT symbol FROM universe WHERE asset_class = ? AND included",
                [asset_class],
            ).fetchall()
        ]

    if not tickers:
        log.warning("no tickers in universe for %s", asset_class)
        return 0

    today = datetime.now(tz=None).date()  # UTC date; avoids deprecated utcnow()
    rows = []
    for i, t in enumerate(tickers, 1):
        try:
            f = fetch_one(t)
        except Exception as e:
            log.warning("[%d/%d] %s fetch failed: %s", i, len(tickers), t, e)
            continue
        rows.append((
            t, today, f["market_cap"], f["pe"], f["forward_pe"], f["pb"],
            f["roe"], f["debt_to_equity"], f["profit_margin"],
            f["sector"], f["industry"],
        ))
        if i % 10 == 0:
            log.info("[%d/%d] %s", i, len(tickers), t)

    if not rows:
        return 0

    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO fundamentals (symbol, as_of, market_cap, pe, forward_pe, pb,
                                      roe, debt_to_equity, profit_margin,
                                      sector, industry, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (symbol, as_of) DO UPDATE SET
                market_cap = excluded.market_cap,
                pe = excluded.pe,
                forward_pe = excluded.forward_pe,
                pb = excluded.pb,
                roe = excluded.roe,
                debt_to_equity = excluded.debt_to_equity,
                profit_margin = excluded.profit_margin,
                sector = excluded.sector,
                industry = excluded.industry,
                fetched_at = now()
            """,
            rows,
        )
    return len(rows)


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="Snapshot fundamentals via yfinance.")
    p.add_argument("--asset-class", default="equity_large",
                   choices=["equity_large", "equity_micro"])
    args = p.parse_args()
    n = ingest_for_asset_class(args.asset_class)
    print(f"\nWrote/updated {n} fundamentals rows.")


if __name__ == "__main__":
    main()
