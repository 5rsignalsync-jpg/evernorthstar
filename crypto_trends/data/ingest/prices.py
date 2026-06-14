"""Binance OHLCV ingestion.

Pulls top-N USDT-quoted spot pairs by 24h quote volume, then fetches recent
klines and upserts into DuckDB. Excludes stablecoin-quoted-against-stablecoin
pairs and leveraged tokens (UP/DOWN/BULL/BEAR).
"""

from __future__ import annotations

import argparse
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import pandas as pd

from crypto_trends.config import settings
from crypto_trends.data.store import connect

log = logging.getLogger(__name__)

KLINE_INTERVAL = "1h"
KLINE_LIMIT = 1000  # Binance max per call

# Bases to exclude from the universe — stablecoins and wrapped/synthetic assets.
STABLE_BASES = {
    "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDP", "USDD",
    "PAX", "USTC", "GUSD", "EUR", "EURI", "AEUR", "USD1",
    "USDUC",  # USDC offshoot stable-ish; ranked highly on volume, no utility
}
LEVERAGED_PATTERN = re.compile(r"(UP|DOWN|BULL|BEAR)USDT$")

# Meme / pure-speculation tokens. Excluded from the `crypto` (utility-focused)
# universe but kept eligible for `crypto_micro` (the moonshot sleeve where the
# whole point is asymmetric meme upside). Curate manually; new memes appear
# constantly. Better to err on inclusion in micro than to pollute majors.
MEME_BASES = {
    # Classic meme tier
    "DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI", "BABYDOGE", "AKITA",
    "MEME", "BOME", "POPCAT", "MEW", "MOG", "GIGA", "WOJAK", "CHILLGUY",
    "FARTCOIN", "MOODENG", "PNUT", "GOAT", "HARRY", "BRETT", "PONKE",
    # Political / personality memes
    "TRUMP", "MAGA", "BIDEN", "MELANIA", "BARRON", "JESUS", "ELON",
    # NFT-collection memecoins
    "PENGU", "MOG", "TROLL", "NOBODY", "PUMP",
    # Generic moon-name memes
    "MOON", "BABY", "TRUMPV2",
}


@dataclass(frozen=True)
class Symbol:
    symbol: str   # "BTCUSDT"
    base: str     # "BTC"
    quote: str    # "USDT"
    quote_volume: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_since(s: str) -> datetime:
    """Parse '30d', '24h', '7d' style duration into an absolute UTC start."""
    m = re.fullmatch(r"(\d+)([dh])", s)
    if not m:
        raise ValueError(f"Bad --since: {s!r}; expected e.g. '30d' or '24h'")
    n, unit = int(m.group(1)), m.group(2)
    delta = timedelta(days=n) if unit == "d" else timedelta(hours=n)
    return _utc_now() - delta


def fetch_universe(
    client: httpx.Client,
    size: int,
    quote: str,
    rank_start: int = 0,
    exclude_memes: bool = False,
) -> list[Symbol]:
    """Return symbols by 24h quote volume in the chosen quote asset.

    `rank_start` skips the first N (0-indexed). `size` is how many to return after
    the skip. Use rank_start=0, size=50 for the majors-only universe; use
    rank_start=30, size=70 for "second-tier" alts that aren't already in the
    major-cap sleeve.

    `exclude_memes=True` filters out known meme/speculation tokens (DOGE, SHIB,
    PEPE, TRUMP, etc.) so the crypto majors sleeve stays utility-focused. The
    Crypto Micro sleeve keeps memes — that's its whole point.
    """
    r = client.get(f"{settings.binance_base_url}/api/v3/ticker/24hr")
    r.raise_for_status()
    rows = r.json()

    candidates: list[Symbol] = []
    for row in rows:
        sym = row["symbol"]
        if not sym.endswith(quote):
            continue
        base = sym[: -len(quote)]
        if base in STABLE_BASES:
            continue
        if exclude_memes and base in MEME_BASES:
            continue
        if LEVERAGED_PATTERN.search(sym):
            continue
        try:
            qv = float(row["quoteVolume"])
        except (TypeError, ValueError):
            continue
        if qv <= 0:
            continue
        candidates.append(Symbol(symbol=sym, base=base, quote=quote, quote_volume=qv))

    candidates.sort(key=lambda s: s.quote_volume, reverse=True)
    return candidates[rank_start : rank_start + size]


def fetch_klines(
    client: httpx.Client, symbol: str, interval: str, start: datetime, end: datetime
) -> pd.DataFrame:
    """Fetch klines for [start, end). Handles paging when range > 1000 bars."""
    all_rows: list[list] = []
    cursor = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    while cursor < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": KLINE_LIMIT,
        }
        for attempt in range(3):
            try:
                r = client.get(
                    f"{settings.binance_base_url}/api/v3/klines",
                    params=params,
                    timeout=15.0,
                )
                r.raise_for_status()
                break
            except httpx.HTTPError as e:
                if attempt == 2:
                    raise
                time.sleep(1.5 ** attempt)
        else:
            raise RuntimeError(f"Unreachable: {e}")  # noqa: F821

        batch = r.json()
        if not batch:
            break
        all_rows.extend(batch)
        # Advance cursor past the last bar's open_time. +1ms avoids re-fetching it.
        last_open = batch[-1][0]
        if len(batch) < KLINE_LIMIT:
            break
        cursor = last_open + 1

    if not all_rows:
        return pd.DataFrame(
            columns=["symbol", "ts", "interval", "open", "high", "low",
                     "close", "volume", "quote_volume", "source"]
        )

    df = pd.DataFrame(
        all_rows,
        columns=["open_time", "open", "high", "low", "close", "volume",
                 "close_time", "quote_volume", "trades", "taker_buy_base",
                 "taker_buy_quote", "ignore"],
    )
    df["symbol"] = symbol
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.tz_localize(None)
    df["interval"] = interval
    df["source"] = "binance"
    for col in ("open", "high", "low", "close", "volume", "quote_volume"):
        df[col] = df[col].astype(float)
    return df[["symbol", "ts", "interval", "open", "high", "low",
               "close", "volume", "quote_volume", "source"]]


def upsert_universe(symbols: list[Symbol], asset_class: str = "crypto") -> None:
    """Replace the universe rows for a specific asset_class with the new set.

    Crucially scoped by `asset_class` — bumping `crypto_micro` must not disturb
    the `crypto` (majors) sleeve and vice versa.
    """
    with connect() as conn:
        conn.execute("BEGIN")
        # Mark only THIS asset class's rows excluded; leave others untouched.
        conn.execute(
            'UPDATE universe SET included = FALSE, updated_at = now() '
            'WHERE asset_class = ?',
            [asset_class],
        )
        rows = [
            (s.symbol, s.base, s.quote, asset_class, i + 1)
            for i, s in enumerate(symbols)
        ]
        conn.executemany(
            """
            INSERT INTO universe (symbol, base, quote, asset_class, "rank",
                                  included, updated_at)
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
        conn.execute("COMMIT")


def upsert_ohlcv(df: pd.DataFrame, asset_class: str = "crypto") -> int:
    if df.empty:
        return 0
    df = df.copy()
    df["asset_class"] = asset_class
    with connect() as conn:
        conn.register("incoming", df)
        conn.execute(
            """
            INSERT INTO ohlcv (symbol, ts, interval, asset_class, open, high,
                               low, close, volume, quote_volume, source)
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


def log_run(source: str, started: datetime, rows: int, status: str, note: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ingest_runs (id, source, started_at, finished_at, rows, status, note)
            VALUES (nextval('ingest_runs_id_seq'), ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            [source, started, rows, status, note],
        )


def ingest(
    since: str,
    size: int,
    rank_start: int = 0,
    asset_class: str = "crypto",
) -> None:
    start = _parse_since(since)
    end = _utc_now()
    started_at = end

    # Majors are utility-focused; Crypto Micro is the moonshot sleeve.
    exclude_memes = (asset_class == "crypto")

    with httpx.Client(timeout=30.0, headers={"User-Agent": "crypto-trends/0.1"}) as client:
        log.info("fetching universe [%s] ranks %d-%d by 24h %s volume "
                 "(exclude_memes=%s)",
                 asset_class, rank_start + 1, rank_start + size,
                 settings.quote_asset, exclude_memes)
        universe = fetch_universe(
            client, size=size, quote=settings.quote_asset,
            rank_start=rank_start, exclude_memes=exclude_memes,
        )
        log.info("universe ready: %d symbols; first 5: %s",
                 len(universe), [s.symbol for s in universe[:5]])
        upsert_universe(universe, asset_class=asset_class)

        total_rows = 0
        for i, sym in enumerate(universe, 1):
            try:
                df = fetch_klines(client, sym.symbol, KLINE_INTERVAL, start, end)
            except httpx.HTTPError as e:
                log.warning("[%d/%d] %s fetch failed: %s",
                            i, len(universe), sym.symbol, e)
                continue
            n = upsert_ohlcv(df, asset_class=asset_class)
            total_rows += n
            log.info("[%d/%d] %s %d bars", i, len(universe), sym.symbol, n)

    log_run("binance", started_at, total_rows, "ok")
    print(f"Done. Inserted/updated {total_rows} bars across {len(universe)} "
          f"{asset_class} symbols.")


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="Ingest Binance OHLCV into DuckDB.")
    p.add_argument("--since", default="30d", help="Lookback window (e.g. 30d, 7d, 24h)")
    p.add_argument("--size", type=int, default=settings.universe_size,
                   help="Universe size (default from config)")
    p.add_argument("--asset-class", default="crypto",
                   choices=["crypto", "crypto_micro"],
                   help="Which sleeve to populate.")
    p.add_argument("--rank-start", type=int, default=None,
                   help="0-indexed rank to start at. Defaults: 0 for crypto, "
                        "30 for crypto_micro (skips majors).")
    args = p.parse_args()

    rank_start = args.rank_start
    if rank_start is None:
        rank_start = 30 if args.asset_class == "crypto_micro" else 0

    ingest(
        since=args.since, size=args.size,
        rank_start=rank_start, asset_class=args.asset_class,
    )


if __name__ == "__main__":
    main()
