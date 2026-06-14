"""News ingestion + FinBERT sentiment scoring (with VADER fallback).

Two free sources:
  - yfinance Ticker.news for equity tickers (per-symbol)
  - 4 RSS feeds for crypto (CoinDesk, CoinTelegraph, Decrypt, TheBlock), tagged
    to base symbols via name/ticker matching

FinBERT (ProsusAI/finbert) is the primary scorer — fine-tuned on financial
news, much better than VADER on domain-specific terminology like "Chapter 11",
"earnings miss", "downgrade". Compound score is `p_pos - p_neg`, in [-1, 1].
VADER is a runtime fallback if FinBERT fails to load.
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime, timezone
from typing import Any

import feedparser
import yfinance as yf

from crypto_trends.data.store import connect
from crypto_trends.signals import finbert

log = logging.getLogger(__name__)

# Free, no-auth RSS feeds covering most crypto news flow.
CRYPTO_RSS_FEEDS = [
    ("CoinDesk",      "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt",       "https://decrypt.co/feed"),
    ("TheBlock",      "https://www.theblock.co/rss.xml"),
]


def _score(text: str) -> float:
    """Single-headline convenience. Prefer _score_batch for many headlines."""
    return finbert.score(text or "")


def _score_batch(texts: list[str]) -> list[float]:
    """Batch-score for ingestion paths — much faster than per-headline."""
    return finbert.score_batch(texts)


# ---------- yfinance (equities) -----------------------------------------------

def _yf_news_for(symbol: str) -> list[dict[str, Any]]:
    """Return normalized {headline, url, publisher, published_at} list.

    Sentiment is *not* set here — call _score_batch on the merged batch in
    ingest_equities() so we score everything in one pass.
    """
    try:
        raw = yf.Ticker(symbol).news or []
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        # yfinance has two shapes depending on version: flat or {'content': {...}}.
        content = item.get("content") if isinstance(item, dict) else None
        if content:
            title = content.get("title")
            url = (content.get("canonicalUrl") or {}).get("url") or content.get("link")
            publisher = (content.get("provider") or {}).get("displayName")
            ts_raw = content.get("pubDate") or content.get("displayTime")
            ts = _parse_iso(ts_raw) if isinstance(ts_raw, str) else None
            if ts is None and isinstance(content.get("providerPublishTime"), int):
                ts = datetime.fromtimestamp(content["providerPublishTime"], tz=timezone.utc)
        else:
            title = item.get("title")
            url = item.get("link")
            publisher = item.get("publisher")
            ts = (datetime.fromtimestamp(item["providerPublishTime"], tz=timezone.utc)
                  if isinstance(item.get("providerPublishTime"), int) else None)

        if not title or ts is None:
            continue
        out.append({
            "headline": title.strip(),
            "url": url,
            "publisher": publisher,
            "published_at": ts.replace(tzinfo=None),  # store naive UTC
        })
    return out


def _parse_iso(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def ingest_equities() -> int:
    with connect(read_only=True) as conn:
        rows = conn.execute(
            "SELECT symbol, asset_class FROM universe "
            "WHERE asset_class IN ('equity_large', 'equity_micro') AND included"
        ).fetchall()

    if not rows:
        return 0

    # First pass: collect raw items per symbol, no scoring yet.
    pending: list[tuple] = []  # (sym, ac, headline, url, publisher, ts)
    for i, (sym, ac) in enumerate(rows, 1):
        items = _yf_news_for(sym)
        for it in items:
            pending.append((sym, ac, it["headline"][:1000], it["url"],
                            it["publisher"], it["published_at"]))
        if i % 20 == 0:
            log.info("[%d/%d] %s (+%d headlines)", i, len(rows), sym, len(items))

    if not pending:
        return 0

    # Second pass: score all headlines in one batched FinBERT call.
    log.info("scoring %d headlines with FinBERT", len(pending))
    scores = _score_batch([p[2] for p in pending])

    batch = [
        (sym, ac, "yfinance", headline, url, publisher, ts, score)
        for (sym, ac, headline, url, publisher, ts), score in zip(pending, scores)
    ]
    return _upsert_news(batch)


# ---------- Crypto news via RSS aggregation -----------------------------------

# Cashtag-like detection: match $BTC, "BTC ", or "Bitcoin"-style names.
# Built once from the universe at ingest time.

_FULLNAME_ALIASES = {
    "BTC": ("Bitcoin",),  "ETH": ("Ethereum", "Ether"), "SOL": ("Solana",),
    "XRP": ("Ripple",),   "ADA": ("Cardano",),          "DOGE": ("Dogecoin",),
    "DOT": ("Polkadot",), "AVAX": ("Avalanche",),       "MATIC": ("Polygon",),
    "LINK": ("Chainlink",),"LTC": ("Litecoin",),        "ATOM": ("Cosmos",),
    "TRX": ("Tron",),     "ICP": ("Internet Computer",),"XLM": ("Stellar",),
    "FIL": ("Filecoin",), "NEAR": ("NEAR Protocol",),   "BCH": ("Bitcoin Cash",),
    "APT": ("Aptos",),    "ARB": ("Arbitrum",),         "OP": ("Optimism",),
}


def _build_matchers(bases: set[str]) -> dict[str, re.Pattern]:
    """Return {base: compiled-regex} where each regex matches any alias for `base`."""
    out: dict[str, re.Pattern] = {}
    for b in bases:
        terms = [re.escape(b)] + [re.escape(a) for a in _FULLNAME_ALIASES.get(b, ())]
        # Word boundary so "ETH" doesn't match "ethereum.org" or "BETH".
        pat = r"\b(" + "|".join(terms) + r")\b"
        out[b] = re.compile(pat, re.IGNORECASE)
    return out


def _parse_feed_time(entry: Any) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None) or entry.get(field) if hasattr(entry, "get") else None
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def ingest_crypto() -> int:
    with connect(read_only=True) as conn:
        rows = conn.execute(
            "SELECT base, symbol FROM universe WHERE asset_class = 'crypto' AND included"
        ).fetchall()

    if not rows:
        return 0

    sym_by_base = dict(rows)
    matchers = _build_matchers(set(sym_by_base))

    # Collect (without scoring) so we can batch-score at the end.
    pending: list[tuple] = []  # (sym, source_label, headline, link, publisher_name, ts)
    for name, url in CRYPTO_RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            log.warning("RSS %s failed: %s", name, e)
            continue
        entries = feed.get("entries", [])
        matched = 0
        for entry in entries:
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            ts = _parse_feed_time(entry)
            if ts is None:
                continue
            link = entry.get("link")
            tagged_bases = [b for b, p in matchers.items() if p.search(title)]
            if not tagged_bases:
                continue
            for base in tagged_bases:
                pending.append((
                    sym_by_base[base], f"rss:{name.lower()}", title[:1000],
                    link, name, ts.replace(tzinfo=None),
                ))
            matched += 1
        log.info("%s: %d entries → %d matched our universe",
                 name, len(entries), matched)

    if not pending:
        return 0

    log.info("scoring %d crypto headlines with FinBERT", len(pending))
    scores = _score_batch([p[2] for p in pending])
    batch = [
        (sym, "crypto", source, headline, link, publisher, ts, score)
        for (sym, source, headline, link, publisher, ts), score in zip(pending, scores)
    ]
    return _upsert_news(batch)


# ---------- shared upsert -----------------------------------------------------

def _upsert_news(batch: list[tuple]) -> int:
    if not batch:
        return 0
    with connect() as conn:
        # DuckDB doesn't have RETURNING on conflict, so count via row diff.
        before = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        conn.executemany(
            """
            INSERT INTO news (id, symbol, asset_class, source, headline, url,
                              publisher, published_at, sentiment)
            VALUES (nextval('news_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol, headline, published_at) DO UPDATE SET
                sentiment = excluded.sentiment,
                url = COALESCE(news.url, excluded.url),
                publisher = COALESCE(news.publisher, excluded.publisher),
                fetched_at = now()
            """,
            batch,
        )
        after = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    return int(after - before)


def rescore_all(batch_size: int = 256) -> int:
    """Re-score every row in `news` with the current sentiment backend.

    Use after upgrading the sentiment model (e.g. VADER → FinBERT) to bring
    historical rows up to current quality. Batched so large tables don't OOM.
    """
    with connect(read_only=True) as conn:
        rows = conn.execute(
            "SELECT id, headline FROM news ORDER BY id"
        ).fetchall()

    if not rows:
        log.info("no news rows to rescore")
        return 0

    log.info("rescoring %d headlines (backend=%s)", len(rows), finbert.backend())
    updated = 0
    for offset in range(0, len(rows), batch_size):
        chunk = rows[offset:offset + batch_size]
        scores = _score_batch([h for _, h in chunk])
        payload = [(s, row_id) for (row_id, _), s in zip(chunk, scores)]
        with connect() as conn:
            conn.executemany("UPDATE news SET sentiment = ? WHERE id = ?", payload)
        updated += len(payload)
        log.info("rescored %d/%d", updated, len(rows))
    return updated


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="Ingest news + score with FinBERT.")
    p.add_argument("--source", default="all",
                   choices=["all", "equities", "crypto"])
    p.add_argument("--rescore", action="store_true",
                   help="Re-score all existing news rows with the current backend. "
                        "Skips fresh ingestion.")
    args = p.parse_args()

    if args.rescore:
        n = rescore_all()
        print(f"\nDone. Rescored {n} rows.")
        return

    total = 0
    if args.source in ("all", "equities"):
        print("Fetching equity news via yfinance…")
        n = ingest_equities()
        print(f"  → {n} new equity headlines")
        total += n
    if args.source in ("all", "crypto"):
        print("Fetching crypto news via RSS aggregation…")
        n = ingest_crypto()
        print(f"  → {n} new crypto headlines (incl. duplicate tag-symbol pairs)")
        total += n

    print(f"\nDone. {total} new news rows.")


if __name__ == "__main__":
    main()
