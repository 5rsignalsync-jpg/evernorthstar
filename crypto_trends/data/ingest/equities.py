"""yfinance equity ingestion.

Pulls daily OHLCV (auto-adjusted for splits/dividends) for both large-cap and
penny-stock universes. Filters penny-stock candidates to actual sub-$5 names
with non-trivial dollar volume (>$1M/day on average), discarding the rest.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

from crypto_trends.data.store import connect
from crypto_trends.data.universes import PENNY_CANDIDATES, SP100, all_equity_universe

logging.getLogger("yfinance").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

PENNY_PRICE_CEILING = 5.0
PENNY_MIN_DOLLAR_VOL = 1_000_000.0   # 20-day avg dollar volume floor


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_since(s: str) -> datetime:
    import re
    m = re.fullmatch(r"(\d+)([dy])", s)
    if not m:
        raise ValueError(f"Bad --since: {s!r}; expected e.g. '180d' or '2y'")
    n, unit = int(m.group(1)), m.group(2)
    delta = timedelta(days=n) if unit == "d" else timedelta(days=n * 365)
    return _utc_now() - delta


def _download(tickers: list[str], start: datetime, end: datetime) -> dict[str, pd.DataFrame]:
    """Batch-download daily bars via yfinance. Returns {ticker: ohlcv_df}."""
    raw = yf.download(
        tickers=tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=True,           # splits + dividends
        group_by="ticker",
        threads=True,
        progress=False,
    )
    if raw is None or raw.empty:
        return {}

    out: dict[str, pd.DataFrame] = {}
    if len(tickers) == 1:
        # Single-ticker form has no MultiIndex.
        df = raw.dropna(how="all")
        if not df.empty:
            out[tickers[0]] = df
        return out

    for t in tickers:
        if t not in raw.columns.get_level_values(0):
            continue
        df = raw[t].dropna(how="all")
        if not df.empty:
            out[t] = df
    return out


def _filter_penny(by_ticker: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Keep only tickers whose last close ≤ $5 and 20d avg dollar volume ≥ $1M."""
    kept: dict[str, pd.DataFrame] = {}
    for t, df in by_ticker.items():
        if df.empty:
            continue
        last_close = df["Close"].iloc[-1]
        if pd.isna(last_close) or last_close > PENNY_PRICE_CEILING:
            continue
        recent = df.tail(20)
        dollar_vol = (recent["Close"] * recent["Volume"]).mean()
        if pd.isna(dollar_vol) or dollar_vol < PENNY_MIN_DOLLAR_VOL:
            continue
        kept[t] = df
    return kept


def _to_long(by_ticker: dict[str, pd.DataFrame], asset_class: str) -> pd.DataFrame:
    """Convert {ticker: ohlcv_df} to a long-format DataFrame matching ohlcv schema."""
    rows = []
    for t, df in by_ticker.items():
        # yfinance names the index "Date" for daily but may use "Datetime" or be
        # unnamed depending on version. Pin it explicitly before resetting.
        df = df.copy()
        df.index.name = "ts"
        df = df.reset_index().rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        ts = pd.to_datetime(df["ts"])
        if getattr(ts.dt, "tz", None) is not None:
            ts = ts.dt.tz_localize(None)
        df["ts"] = ts
        df["symbol"] = t
        df["interval"] = "1d"
        df["source"] = "yfinance"
        df["asset_class"] = asset_class
        df["quote_volume"] = df["close"] * df["volume"]
        rows.append(df[["symbol", "ts", "interval", "asset_class",
                        "open", "high", "low", "close", "volume",
                        "quote_volume", "source"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def upsert_universe(tickers: list[str], asset_class: str, ranks: dict[str, int]) -> None:
    """Upsert tickers into universe, marking the given asset_class & rank."""
    with connect() as conn:
        # Reset included=FALSE for everything in this asset_class first.
        conn.execute(
            "UPDATE universe SET included = FALSE WHERE asset_class = ?",
            [asset_class],
        )
        rows = [
            (t, t, "USD", asset_class, ranks.get(t, 9999))
            for t in tickers
        ]
        conn.executemany(
            """
            INSERT INTO universe (symbol, base, quote, asset_class, "rank", included, updated_at)
            VALUES (?, ?, ?, ?, ?, TRUE, now())
            ON CONFLICT (symbol) DO UPDATE SET
                base = excluded.base,
                quote = excluded.quote,
                asset_class = excluded.asset_class,
                "rank" = excluded."rank",
                included = TRUE,
                updated_at = now()
            """,
            rows,
        )


def upsert_ohlcv(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    with connect() as conn:
        conn.register("incoming", df)
        conn.execute(
            """
            INSERT INTO ohlcv (symbol, ts, interval, asset_class, open, high, low,
                               close, volume, quote_volume, source)
            SELECT symbol, ts, interval, asset_class, open, high, low,
                   close, volume, quote_volume, source FROM incoming
            ON CONFLICT (symbol, ts, interval, source) DO UPDATE SET
                asset_class = excluded.asset_class,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                quote_volume = excluded.quote_volume
            """
        )
        conn.unregister("incoming")
    return len(df)


def ingest_large(since: datetime, end: datetime) -> int:
    log.info("fetching %d large-cap tickers via yfinance", len(SP100))
    bars = _download(SP100, since, end)
    log.info("yfinance returned data for %d/%d large caps", len(bars), len(SP100))
    if not bars:
        return 0
    df = _to_long(bars, "equity_large")
    n = upsert_ohlcv(df)
    ranks = {t: i + 1 for i, t in enumerate(SP100)}
    upsert_universe(list(bars.keys()), "equity_large", ranks)
    return n


def ingest_penny(since: datetime, end: datetime, candidates: list[str] | None = None) -> int:
    tickers = candidates if candidates is not None else PENNY_CANDIDATES
    log.info("fetching %d penny-stock candidates via yfinance", len(tickers))
    bars = _download(tickers, since, end)
    log.info("yfinance returned data for %d/%d candidates", len(bars), len(tickers))
    bars = _filter_penny(bars)
    log.info("%d candidates pass <$%s + $%sM ADV filter",
             len(bars), PENNY_PRICE_CEILING, PENNY_MIN_DOLLAR_VOL / 1e6)
    if not bars:
        return 0
    df = _to_long(bars, "equity_micro")
    n = upsert_ohlcv(df)
    ranks = {t: i + 1 for i, t in enumerate(bars.keys())}
    upsert_universe(list(bars.keys()), "equity_micro", ranks)
    return n


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="Ingest equity OHLCV via yfinance.")
    p.add_argument("--since", default="365d", help="Lookback window (e.g. 365d, 2y).")
    p.add_argument("--sleeve", choices=["large", "penny", "both"], default="both")
    p.add_argument("--use-screener", action="store_true",
                   help="For the penny sleeve, run the live screener to discover "
                        "candidates instead of using the hardcoded list. Slower (~3-10 min) "
                        "but the universe stays fresh.")
    args = p.parse_args()

    start = _parse_since(args.since)
    end = _utc_now()

    total = 0
    if args.sleeve in ("large", "both"):
        total += ingest_large(start, end)
    if args.sleeve in ("penny", "both"):
        candidates: list[str] | None = None
        if args.use_screener:
            from crypto_trends.data.screener import screen_penny_stocks
            log.info("running live penny screener (--use-screener)")
            candidates = screen_penny_stocks()
        total += ingest_penny(start, end, candidates=candidates)
    print(f"\nDone. Inserted/updated {total} equity bars.")


if __name__ == "__main__":
    main()
