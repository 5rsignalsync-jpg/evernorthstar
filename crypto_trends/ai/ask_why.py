"""'Ask why' — given a symbol, summarize recent news + price action + signal
changes + smart-money moves into a short human explanation.

Triggered from the drilldown modal. Pro-tier gated at the route level.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from crypto_trends.ai import claude
from crypto_trends.data.store import connect


SYSTEM_PROMPT = """You are a finance research assistant for the EverNorthstar dashboard.

You explain WHY a ticker is moving in 4-6 short sentences, plain English, no jargon for retail
investors. You cite specific facts from the data provided (price moves, headlines, smart-money
moves). You NEVER invent data. If the data is thin, say so honestly.

Tone: direct, honest, like explaining to a smart friend. No emojis. No marketing
fluff. No "remember to consult a financial advisor" boilerplate — the app already
has that disclaimer.

End with a one-line caveat about what the data DOESN'T show (e.g., "13F lag is
45 days so positions could already be unwound" or "news sentiment is recent but
limited to last 7 days").
"""


def _gather_context(symbol: str, asset_class: str) -> dict:
    """Pull the freshest data we have for this ticker from DuckDB.

    Returns a dict with: prices (last 14 days), headlines (last 7 days),
    signal_history (last 14 scored windows), smart_money (recent activity if any).
    """
    with connect(read_only=True) as conn:
        # The base symbol (AAPL, BTC) may differ from the row key (AAPLUSDT). Use either.
        rows = conn.execute(
            "SELECT base FROM universe WHERE symbol = ? OR base = ? LIMIT 1",
            [symbol, symbol],
        ).fetchone()
        base = rows[0] if rows else symbol

        prices = conn.execute(
            """
            SELECT ts, close, volume
            FROM ohlcv
            WHERE (symbol = ? OR symbol = ?)
              AND ts >= now() - INTERVAL '14 days'
            ORDER BY ts DESC LIMIT 60
            """,
            [symbol, base],
        ).fetchall()

        headlines = conn.execute(
            """
            SELECT published_at, headline, publisher, sentiment
            FROM news
            WHERE (symbol = ? OR symbol = ?)
              AND published_at >= now() - INTERVAL '7 days'
            ORDER BY published_at DESC LIMIT 12
            """,
            [symbol, base],
        ).fetchall()

        signal_history = conn.execute(
            """
            SELECT ts, signal_name, score
            FROM signal_scores
            WHERE (symbol = ? OR symbol = ?)
              AND ts >= now() - INTERVAL '14 days'
            ORDER BY ts DESC LIMIT 20
            """,
            [symbol, base],
        ).fetchall()

        smart_money = conn.execute(
            """
            SELECT disclosure_date, actor_name, side, amount_min, source
            FROM smart_money_trades
            WHERE ticker = ?
              AND disclosure_date >= now() - INTERVAL '90 days'
            ORDER BY disclosure_date DESC LIMIT 8
            """,
            [base],
        ).fetchall()

    return {
        "base": base,
        "asset_class": asset_class,
        "prices": prices,
        "headlines": headlines,
        "signal_history": signal_history,
        "smart_money": smart_money,
    }


def _format_context(ctx: dict) -> str:
    """Render the gathered data into a compact text block for Claude."""
    out = [f"Ticker: {ctx['base']} ({ctx['asset_class']})", ""]

    if ctx["prices"]:
        latest_close = ctx["prices"][0][1]
        oldest_close = ctx["prices"][-1][1]
        pct_change = (latest_close / oldest_close - 1) * 100 if oldest_close else 0
        out.append(
            f"PRICES (last {len(ctx['prices'])} bars, ~14 days):"
        )
        out.append(
            f"  Current close: ${latest_close:.4f} "
            f"({pct_change:+.2f}% over the window)"
        )
        out.append(f"  Oldest close in window: ${oldest_close:.4f}")
        out.append("")

    if ctx["headlines"]:
        out.append("RECENT HEADLINES (FinBERT sentiment in parens, -1 to +1):")
        for ts, hl, pub, sent in ctx["headlines"]:
            sent_str = f"{sent:+.2f}" if sent is not None else "n/a"
            out.append(f"  [{ts.date()}] ({sent_str}) {pub}: {hl}")
        out.append("")
    else:
        out.append("RECENT HEADLINES: (none in the last 7 days)")
        out.append("")

    if ctx["signal_history"]:
        latest_score = ctx["signal_history"][0][2]
        oldest_score = ctx["signal_history"][-1][2]
        out.append(
            "SIGNAL HISTORY (cross-sectional momentum, -1 worst to +1 best):"
        )
        out.append(f"  Most recent: {latest_score:+.3f}")
        out.append(f"  14 days ago: {oldest_score:+.3f}")
        out.append("")

    if ctx["smart_money"]:
        out.append("SMART-MONEY ACTIVITY (last 90 days, lag-aware):")
        for date, actor, side, amount, source in ctx["smart_money"]:
            amt = f"${amount/1e6:.1f}M" if amount else "n/a"
            out.append(f"  [{date}] {actor} {side} {amt} via {source}")
        out.append("")
    else:
        out.append("SMART-MONEY ACTIVITY: (no recent 13F/insider/Congress disclosures)")
        out.append("")

    return "\n".join(out)


def ask_why(symbol: str, asset_class: str) -> Optional[str]:
    """Returns a 4-6 sentence explanation, or None if AI is disabled or
    data is too thin to say anything meaningful."""
    if not claude.is_enabled():
        return None
    ctx = _gather_context(symbol, asset_class)
    if not ctx["prices"] and not ctx["headlines"] and not ctx["smart_money"]:
        # Nothing to explain
        return None
    context_block = _format_context(ctx)
    user_prompt = (
        f"Explain in 4-6 sentences why {ctx['base']} is moving the way it is, "
        f"based ONLY on the data below. Be specific — cite at least one fact.\n\n"
        f"{context_block}"
    )
    return claude.ask(SYSTEM_PROMPT, user_prompt, max_tokens=500)
