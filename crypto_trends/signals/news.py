"""news_v1: per-symbol buzz + sentiment + negative-event flag.

This is a *secondary* signal — not a primary alpha. It's designed to:
  - Filter out longs that just got negative news ("don't go long the stock that just
    got delisted").
  - Surface unusual attention (buzz) as a tie-breaker when momentum scores are close.
  - Make ranking outputs explainable via the headline column.

VADER is the underlying sentiment model. It's known to be brittle on financial
headlines (sarcasm, contrarian phrasings, negation). Treat sentiment as
low-confidence; treat the negative_event keyword filter as higher-confidence.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import NamedTuple

import pandas as pd

from crypto_trends.data.store import connect

SIGNAL_NAME = "news_v1"

# Keywords that strongly suggest a negative event regardless of VADER score.
# Designed for *false-negative-tolerance* — we'd rather miss some negatives than
# falsely flag positives.
NEGATIVE_KEYWORDS = [
    "fraud", "investigation", "delisting", "delisted", "lawsuit", "subpoena",
    "bankruptcy", "halted", "halt", "sec charges", "doj", "indictment",
    "indicted", "hack", "exploit", "rug pull", "ponzi", "guilty", "fined",
    "settlement", "restated", "going concern", "chapter 11",
]
_NEG_PATTERN_CACHE: list[str] = [k.lower() for k in NEGATIVE_KEYWORDS]


class NewsSignal(NamedTuple):
    symbol: str
    buzz: int                # count of headlines in window
    buzz_z: float            # z-score across universe at this asset_class
    sentiment_avg: float     # mean VADER compound in window
    sentiment_z: float       # z-score across universe at this asset_class
    negative_event: bool     # any flagged headline in window
    recent_headline: str | None
    recent_headline_at: datetime | None


def _flag_negative(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _NEG_PATTERN_CACHE)


def compute_for_asset_class(
    asset_class: str,
    window_hours: int | None = None,
) -> dict[str, NewsSignal]:
    """Compute news_v1 for every symbol currently in the universe."""
    if window_hours is None:
        window_hours = 6 if asset_class == "crypto" else 24

    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    with connect(read_only=True) as conn:
        symbols = [r[0] for r in conn.execute(
            "SELECT symbol FROM universe WHERE asset_class = ? AND included",
            [asset_class],
        ).fetchall()]
        if not symbols:
            return {}

        df = conn.execute(
            """
            SELECT n.symbol, n.headline, n.published_at, n.sentiment
            FROM news n
            JOIN universe u ON u.symbol = n.symbol
            WHERE u.asset_class = ?
              AND u.included
              AND n.published_at >= ?
            ORDER BY n.published_at DESC
            """,
            [asset_class, cutoff],
        ).fetchdf()

    # Per-symbol aggregates.
    by_sym: dict[str, dict] = {s: {"count": 0, "sum_sent": 0.0,
                                    "neg": False, "latest": None,
                                    "latest_at": None}
                                for s in symbols}
    for row in df.itertuples(index=False):
        s = row.symbol
        agg = by_sym[s]
        agg["count"] += 1
        if row.sentiment is not None and not pd.isna(row.sentiment):
            agg["sum_sent"] += float(row.sentiment)
        if _flag_negative(row.headline):
            agg["neg"] = True
        if agg["latest_at"] is None or row.published_at > agg["latest_at"]:
            agg["latest"] = row.headline
            agg["latest_at"] = row.published_at

    # Cross-sectional z-scoring on buzz and sentiment.
    counts = pd.Series({s: by_sym[s]["count"] for s in symbols}, dtype=float)
    sents = pd.Series(
        {s: (by_sym[s]["sum_sent"] / by_sym[s]["count"]) if by_sym[s]["count"] else 0.0
         for s in symbols},
        dtype=float,
    )

    def _z(s: pd.Series) -> pd.Series:
        mu, sd = s.mean(), s.std()
        if sd == 0 or pd.isna(sd):
            return pd.Series(0.0, index=s.index)
        return (s - mu) / sd

    buzz_z = _z(counts)
    sent_z = _z(sents)

    return {
        s: NewsSignal(
            symbol=s,
            buzz=int(by_sym[s]["count"]),
            buzz_z=float(buzz_z[s]),
            sentiment_avg=float(sents[s]),
            sentiment_z=float(sent_z[s]),
            negative_event=bool(by_sym[s]["neg"]),
            recent_headline=by_sym[s]["latest"],
            recent_headline_at=by_sym[s]["latest_at"],
        )
        for s in symbols
    }
