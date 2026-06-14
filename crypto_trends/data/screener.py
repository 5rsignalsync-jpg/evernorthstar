"""Penny-stock screener.

Pulls the official NASDAQ + NYSE listings, filters out non-common-stock
instruments (warrants, ETFs, preferreds, rights, units, test issues), then
fetches the last 30 days of daily bars to keep only names trading at or below
$5 with average daily dollar volume above the configured floor.

Run nightly. The output universe rotates as cheap names rise above $5 or
illiquid names fall below the $ADV cutoff. Replaces the hardcoded
PENNY_CANDIDATES list in data/universes.py.
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime, timedelta, timezone
from io import StringIO

import httpx
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

NASDAQ_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

# Suffix patterns indicating non-common-stock instruments we want to skip.
NON_COMMON_SUFFIX = re.compile(r"[.\-$].*$|[WRPU]$")

DEFAULT_MAX_PRICE = 5.0
DEFAULT_MIN_DOLLAR_VOL = 1_000_000.0
DEFAULT_LIMIT = 400        # cap final universe size
DEFAULT_CANDIDATE_CAP = 1500    # cap tickers we download bars for


def _fetch_listing_text(client: httpx.Client, url: str) -> str:
    r = client.get(url, timeout=30.0)
    r.raise_for_status()
    return r.text


def fetch_listings() -> pd.DataFrame:
    """Return concatenated NASDAQ + NYSE listings as a DataFrame.

    Columns we care about: Symbol, Security Name, ETF, Test Issue.
    """
    rows: list[pd.DataFrame] = []
    with httpx.Client(headers={"User-Agent": "crypto-trends/0.1"}) as client:
        for url in (NASDAQ_LISTED, OTHER_LISTED):
            log.info("fetching listing: %s", url)
            text = _fetch_listing_text(client, url)
            # Drop the "File Creation Time" footer line.
            lines = [ln for ln in text.splitlines()
                     if ln and not ln.startswith("File Creation Time")]
            df = pd.read_csv(StringIO("\n".join(lines)), sep="|", dtype=str)
            rows.append(df)

    combined = pd.concat(rows, ignore_index=True, sort=False)

    # Normalize. otherlisted.txt uses "ACT Symbol", nasdaqlisted.txt uses "Symbol".
    if "Symbol" not in combined.columns and "ACT Symbol" in combined.columns:
        combined = combined.rename(columns={"ACT Symbol": "Symbol"})
    if "ACT Symbol" in combined.columns and "Symbol" in combined.columns:
        combined["Symbol"] = combined["Symbol"].fillna(combined["ACT Symbol"])

    for col in ("ETF", "Test Issue"):
        if col not in combined.columns:
            combined[col] = "N"

    return combined[["Symbol", "Security Name", "ETF", "Test Issue"]].dropna(subset=["Symbol"])


def filter_common_stock(df: pd.DataFrame) -> list[str]:
    """Return ticker symbols likely to be common stock (skip warrants/ETFs/etc.)."""
    keep = (
        (df["Test Issue"].fillna("N").str.upper() == "N")
        & (df["ETF"].fillna("N").str.upper() == "N")
    )
    df = df[keep]

    symbols: list[str] = []
    for sym in df["Symbol"].dropna().astype(str):
        sym = sym.strip().upper()
        if not sym or len(sym) > 5:
            continue
        if NON_COMMON_SUFFIX.search(sym):
            continue
        symbols.append(sym)
    return sorted(set(symbols))


def _avg_dollar_volume(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    tail = df.tail(20)
    val = (tail["Close"] * tail["Volume"]).mean()
    return float(val) if pd.notna(val) else 0.0


def screen_penny_stocks(
    max_price: float = DEFAULT_MAX_PRICE,
    min_dollar_vol: float = DEFAULT_MIN_DOLLAR_VOL,
    limit: int = DEFAULT_LIMIT,
    candidate_cap: int = DEFAULT_CANDIDATE_CAP,
    download_chunk: int = 200,
) -> list[str]:
    """Run the full screen and return the resulting ticker list.

    candidate_cap bounds the number of yfinance downloads we'll attempt — the
    full universe of ~6k symbols is too slow to batch-fetch every refresh.
    """
    listings = fetch_listings()
    candidates = filter_common_stock(listings)
    log.info("listings → %d common-stock candidates after filtering",
             len(candidates))

    if candidate_cap and len(candidates) > candidate_cap:
        # Deterministic but spread coverage across the alphabet (stride).
        stride = max(1, len(candidates) // candidate_cap)
        candidates = candidates[::stride][:candidate_cap]
        log.info("capped to %d candidates via stride sampling", len(candidates))

    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=45)
    start_s = start.strftime("%Y-%m-%d")
    end_s = end.strftime("%Y-%m-%d")

    passing: list[tuple[str, float, float]] = []  # (sym, last_close, adv)
    for i in range(0, len(candidates), download_chunk):
        chunk = candidates[i : i + download_chunk]
        log.info("downloading bars [%d/%d]…",
                 min(i + download_chunk, len(candidates)), len(candidates))
        try:
            raw = yf.download(
                tickers=chunk, start=start_s, end=end_s,
                interval="1d", auto_adjust=True, group_by="ticker",
                threads=True, progress=False,
            )
        except Exception as e:
            log.warning("chunk download failed: %s", e)
            continue
        if raw is None or raw.empty:
            continue

        for t in chunk:
            try:
                if len(chunk) == 1:
                    sub = raw.dropna(how="all")
                else:
                    if t not in raw.columns.get_level_values(0):
                        continue
                    sub = raw[t].dropna(how="all")
            except (KeyError, AttributeError):
                continue
            if sub.empty:
                continue
            last_close = sub["Close"].iloc[-1]
            if pd.isna(last_close) or last_close > max_price or last_close <= 0:
                continue
            adv = _avg_dollar_volume(sub)
            if adv < min_dollar_vol:
                continue
            passing.append((t, float(last_close), adv))

    # Rank by dollar volume — the most-liquid penny names first.
    passing.sort(key=lambda x: x[2], reverse=True)
    selected = [t for t, _, _ in passing[:limit]]
    log.info("screen result: %d names pass price + ADV filters; keeping top %d",
             len(passing), len(selected))
    return selected


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="Penny-stock screener.")
    p.add_argument("--max-price", type=float, default=DEFAULT_MAX_PRICE)
    p.add_argument("--min-dollar-vol", type=float, default=DEFAULT_MIN_DOLLAR_VOL)
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--candidate-cap", type=int, default=DEFAULT_CANDIDATE_CAP)
    args = p.parse_args()

    tickers = screen_penny_stocks(
        max_price=args.max_price,
        min_dollar_vol=args.min_dollar_vol,
        limit=args.limit,
        candidate_cap=args.candidate_cap,
    )
    print(f"\nScreened {len(tickers)} penny-stock candidates:")
    for t in tickers[:30]:
        print(f"  {t}")
    if len(tickers) > 30:
        print(f"  ... (+{len(tickers) - 30} more)")


if __name__ == "__main__":
    main()
