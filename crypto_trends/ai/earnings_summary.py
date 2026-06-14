"""AI earnings summary — what happened around a ticker's last earnings report.

Instead of paying for transcript APIs ($14-50/mo), we synthesize a summary
from data we already have:
  - The earnings date itself (from data/ingest/earnings.py)
  - Post-earnings headlines (last 5 days from `news`)
  - Price reaction (% move in the 1d and 5d windows after earnings)
  - Signal score change (momentum_v1 before vs after)

Claude reads all of that and writes a 4-6 sentence summary covering:
  - Bottom-line beat/miss vibe (from headlines)
  - Market reaction (price move)
  - Forward outlook tone (from headlines)
  - One honest caveat about what we DON'T have (no transcript = no exact quotes)

Summaries are cached in DuckDB so we don't pay Claude $0.001 every page view.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from crypto_trends.ai import claude
from crypto_trends.data.store import connect

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are EverNorthstar's earnings recap writer.

Given a structured snapshot of headlines, price action, and signal changes
around a company's earnings report, write a 4-6 sentence summary covering:
  1. Beat or miss (inferred from headline tone — be honest if signals are mixed)
  2. The market's reaction (price move %)
  3. Forward outlook themes from headlines (raised guidance? supply chain? capital return?)
  4. One concrete fact users can act on or remember

No emojis. No marketing fluff. No financial advice. End with one short caveat
about what's NOT in the data (e.g., "no transcript was processed — exact
management quotes are not included").
"""


def _gather(symbol: str, base: str, earnings_date: str) -> dict:
    """Pull headlines + prices + signal scores around the earnings date."""
    with connect(read_only=True) as conn:
        # Headlines in the 5 days following the earnings date
        headlines = conn.execute(
            """
            SELECT published_at, headline, publisher, sentiment
            FROM news
            WHERE (symbol = ? OR symbol = ?)
              AND published_at >= ?
              AND published_at <= ? + INTERVAL '5 days'
            ORDER BY published_at ASC LIMIT 20
            """,
            [symbol, base, earnings_date, earnings_date],
        ).fetchall()

        # Price reaction — closes on earnings date and +1d/+5d after
        prices = conn.execute(
            """
            SELECT ts, close
            FROM ohlcv
            WHERE (symbol = ? OR symbol = ?)
              AND ts >= ? - INTERVAL '1 day'
              AND ts <= ? + INTERVAL '7 days'
            ORDER BY ts ASC
            """,
            [symbol, base, earnings_date, earnings_date],
        ).fetchall()

        # Signal score before vs after
        score_before = conn.execute(
            """
            SELECT score FROM signal_scores
            WHERE (symbol = ? OR symbol = ?)
              AND signal_name = 'momentum_v1' AND ts <= ?
            ORDER BY ts DESC LIMIT 1
            """,
            [symbol, base, earnings_date],
        ).fetchone()

        score_after = conn.execute(
            """
            SELECT score FROM signal_scores
            WHERE (symbol = ? OR symbol = ?)
              AND signal_name = 'momentum_v1' AND ts >= ? + INTERVAL '2 days'
            ORDER BY ts ASC LIMIT 1
            """,
            [symbol, base, earnings_date],
        ).fetchone()

    return {
        "symbol": symbol,
        "base": base,
        "earnings_date": str(earnings_date),
        "headlines": headlines,
        "prices": prices,
        "score_before": score_before[0] if score_before else None,
        "score_after": score_after[0] if score_after else None,
    }


def _format_context(ctx: dict) -> str:
    out = [f"Ticker: {ctx['base']}", f"Earnings date: {ctx['earnings_date']}", ""]

    if ctx["prices"] and len(ctx["prices"]) >= 2:
        closes = [p[1] for p in ctx["prices"]]
        # Use first close as pre-earnings baseline, look at +1d and final
        baseline = closes[0]
        out.append("PRICE REACTION:")
        out.append(f"  Pre-earnings close (~T-1): ${baseline:.2f}")
        if len(closes) >= 2:
            next_close = closes[1]
            pct = (next_close / baseline - 1) * 100
            out.append(f"  T+1 close: ${next_close:.2f} ({pct:+.2f}%)")
        if len(closes) >= 4:
            last_close = closes[-1]
            pct_total = (last_close / baseline - 1) * 100
            out.append(f"  T+5 close: ${last_close:.2f} ({pct_total:+.2f}%)")
        out.append("")

    if ctx["score_before"] is not None or ctx["score_after"] is not None:
        out.append("SIGNAL SCORE CHANGE (momentum_v1, -1 to +1):")
        out.append(f"  Before: {ctx['score_before']:+.3f}" if ctx["score_before"] is not None else "  Before: n/a")
        out.append(f"  After:  {ctx['score_after']:+.3f}" if ctx["score_after"] is not None else "  After: n/a")
        out.append("")

    if ctx["headlines"]:
        out.append(f"POST-EARNINGS HEADLINES (next 5 days, {len(ctx['headlines'])} total):")
        for ts, hl, pub, sent in ctx["headlines"]:
            sent_str = f"{sent:+.2f}" if sent is not None else "n/a"
            out.append(f"  [{ts.date()}] ({sent_str}) {pub}: {hl}")
    else:
        out.append("POST-EARNINGS HEADLINES: (none in the 5-day window — data may be thin)")
    return "\n".join(out)


def _persist_summary(
    symbol: str, base: str, earnings_date: str, summary: str, model_version: str
) -> None:
    """Cache the summary so future requests for the same earnings event hit
    the cache, not Claude. PRIMARY KEY (base, earnings_date) ensures one row
    per company per call."""
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_summaries (
              base VARCHAR NOT NULL,
              earnings_date DATE NOT NULL,
              symbol VARCHAR,
              summary TEXT NOT NULL,
              model_version VARCHAR,
              generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (base, earnings_date)
            )
            """
        )
        # Upsert pattern — INSERT or REPLACE
        conn.execute(
            "DELETE FROM earnings_summaries WHERE base = ? AND earnings_date = ?",
            [base, earnings_date],
        )
        conn.execute(
            """INSERT INTO earnings_summaries
               (base, earnings_date, symbol, summary, model_version, generated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [base, earnings_date, symbol, summary, model_version, datetime.utcnow()],
        )


def _read_cached_summary(base: str, earnings_date: str) -> Optional[dict]:
    with connect(read_only=True) as conn:
        try:
            row = conn.execute(
                """SELECT summary, model_version, generated_at
                   FROM earnings_summaries
                   WHERE base = ? AND earnings_date = ?""",
                [base, earnings_date],
            ).fetchone()
        except Exception:
            return None
    if not row:
        return None
    return {
        "summary": row[0],
        "model_version": row[1],
        "generated_at": str(row[2]),
        "cached": True,
    }


def _resolve_latest_earnings_date(symbol: str, base: str) -> Optional[str]:
    """Find the most recent earnings date for this ticker, from our calendar
    or from headlines that mentioned 'earnings'/'reports'/'Q1'/'Q2' etc."""
    with connect(read_only=True) as conn:
        # We may have an earnings_calendar table from data/ingest/earnings.py
        try:
            row = conn.execute(
                """
                SELECT max(earnings_date)
                FROM earnings_calendar
                WHERE (symbol = ? OR symbol = ?)
                  AND earnings_date <= now()
                """,
                [symbol, base],
            ).fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
            pass
        return None


def summarize_latest_earnings(symbol: str) -> Optional[dict]:
    """Generate (or return cached) summary for the ticker's most recent
    earnings event. Returns None if AI is disabled, no earnings on file,
    or data is too thin.

    Returns: {summary, earnings_date, model_version, generated_at, cached}
    """
    if not claude.is_enabled():
        return None

    # Resolve the canonical base symbol (AAPL vs AAPLUSDT etc.)
    with connect(read_only=True) as conn:
        row = conn.execute(
            "SELECT base FROM universe WHERE symbol = ? OR base = ? LIMIT 1",
            [symbol, symbol],
        ).fetchone()
    base = row[0] if row else symbol

    earnings_date = _resolve_latest_earnings_date(symbol, base)
    if not earnings_date:
        return None

    cached = _read_cached_summary(base, earnings_date)
    if cached:
        return {**cached, "earnings_date": earnings_date}

    ctx = _gather(symbol, base, earnings_date)
    # Bail if we have nothing useful to summarize
    if not ctx["headlines"] and not ctx["prices"]:
        return None

    context_block = _format_context(ctx)
    user_prompt = (
        f"Summarize {base}'s most recent earnings event ({earnings_date}) in "
        f"4-6 sentences, plain English, based ONLY on the data below.\n\n"
        f"{context_block}"
    )
    text = claude.ask(SYSTEM_PROMPT, user_prompt, max_tokens=500)
    if not text:
        return None

    from crypto_trends.config import settings
    _persist_summary(symbol, base, earnings_date, text, settings.anthropic_model)
    return {
        "summary": text,
        "earnings_date": earnings_date,
        "model_version": settings.anthropic_model,
        "generated_at": datetime.utcnow().isoformat(),
        "cached": False,
    }
