"""AI-generated morning digest.

Builds a personalized 'what happened overnight' email by:
  1. Pulling the top 5 long + top 5 short rankings from each sleeve
  2. Pulling the freshest smart-money disclosures (last 24h)
  3. Pulling biggest sentiment-shift headlines (last 24h)
  4. Handing the structured snapshot to Claude and asking for a tight
     5-bullet summary in plain English
  5. Wrapping the summary + a 'further reading' table in branded HTML

Designed to run from a cron (see scripts/send_digest.py) at ~7am ET. Gated
on both ANTHROPIC_API_KEY (for the summary) and RESEND_API_KEY (for delivery).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from crypto_trends.ai import claude
from crypto_trends.data.store import connect

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are EverNorthstar's morning digest writer.

Given a structured snapshot of overnight market data, write a 5-bullet
'what to know' summary for retail investors. Each bullet is 1-2 short
sentences. No emojis. No marketing fluff. No financial advice. Cite specific
tickers and numbers from the data. If a category is empty (e.g., no smart-money
activity), skip it rather than padding.

Order bullets by importance: outliers first, then sleeve highlights, then
smart-money activity, then news. Close with one honest caveat about what
the data doesn't show.
"""


@dataclass
class DigestSnapshot:
    top_movers: list[dict]              # across all sleeves
    smart_money_recent: list[dict]      # last 24h disclosures
    notable_headlines: list[dict]       # biggest sentiment shifts
    sleeves: dict[str, dict]            # per-sleeve longs/shorts


def gather_snapshot() -> DigestSnapshot:
    """Pull the data the digest summarizes. Read-only DuckDB connection."""
    with connect(read_only=True) as conn:
        # Per-sleeve top 5 longs + shorts from the most-recent rankings batch.
        # asset_class lives on universe, not signal_scores — join is required.
        sleeves: dict[str, dict] = {}
        for sleeve in ("crypto", "crypto_micro", "equity_large", "equity_micro"):
            try:
                rows = conn.execute(
                    """
                    WITH latest AS (
                        SELECT max(s.ts) AS ts
                        FROM signal_scores s
                        JOIN universe u ON u.symbol = s.symbol
                        WHERE u.asset_class = ? AND s.signal_name = 'momentum_v1'
                    )
                    SELECT s.symbol, s.score
                    FROM signal_scores s
                    JOIN universe u ON u.symbol = s.symbol
                    WHERE u.asset_class = ?
                      AND s.signal_name = 'momentum_v1'
                      AND s.ts = (SELECT ts FROM latest)
                    ORDER BY s.score DESC
                    """,
                    [sleeve, sleeve],
                ).fetchall()
            except Exception as e:
                log.warning("snapshot: sleeve %s skipped: %s", sleeve, e)
                continue
            if not rows:
                continue
            sleeves[sleeve] = {
                "longs": [{"symbol": r[0], "score": r[1]} for r in rows[:5]],
                "shorts": [{"symbol": r[0], "score": r[1]} for r in rows[-5:][::-1]],
            }

        # Top movers across everything — biggest 5 absolute scores.
        top_movers_rows = []
        try:
            top_movers_rows = conn.execute(
                """
                WITH latest_per_class AS (
                    SELECT u.asset_class, max(s.ts) AS ts
                    FROM signal_scores s
                    JOIN universe u ON u.symbol = s.symbol
                    WHERE s.signal_name = 'momentum_v1'
                    GROUP BY u.asset_class
                )
                SELECT s.symbol, u.asset_class, s.score
                FROM signal_scores s
                JOIN universe u ON u.symbol = s.symbol
                JOIN latest_per_class l
                  ON u.asset_class = l.asset_class AND s.ts = l.ts
                WHERE s.signal_name = 'momentum_v1'
                ORDER BY abs(s.score) DESC LIMIT 8
                """,
            ).fetchall()
        except Exception as e:
            log.warning("snapshot: top movers query failed: %s", e)

        smart_money_rows = []
        try:
            smart_money_rows = conn.execute(
                """
                SELECT ticker, actor_name, side, amount_min, source, disclosure_date
                FROM smart_money_trades
                WHERE disclosure_date >= now() - INTERVAL '1 day'
                ORDER BY amount_min DESC NULLS LAST
                LIMIT 6
                """,
            ).fetchall()
        except Exception as e:
            log.warning("snapshot: smart money query failed: %s", e)

        headlines_rows = []
        try:
            headlines_rows = conn.execute(
                """
                SELECT symbol, published_at, headline, publisher, sentiment
                FROM news
                WHERE published_at >= now() - INTERVAL '1 day'
                  AND sentiment IS NOT NULL
                ORDER BY abs(sentiment) DESC LIMIT 6
                """,
            ).fetchall()
        except Exception as e:
            log.warning("snapshot: headlines query failed: %s", e)

    return DigestSnapshot(
        top_movers=[
            {"symbol": r[0], "asset_class": r[1], "score": r[2]}
            for r in top_movers_rows
        ],
        smart_money_recent=[
            {
                "ticker": r[0], "actor": r[1], "side": r[2],
                "amount": r[3], "source": r[4], "date": str(r[5]),
            }
            for r in smart_money_rows
        ],
        notable_headlines=[
            {
                "symbol": r[0], "date": str(r[1]), "headline": r[2],
                "publisher": r[3], "sentiment": r[4],
            }
            for r in headlines_rows
        ],
        sleeves=sleeves,
    )


def _format_snapshot_for_claude(snap: DigestSnapshot) -> str:
    out = ["MARKET SNAPSHOT (last 24h):", ""]
    if snap.top_movers:
        out.append("TOP MOVERS BY |score|:")
        for m in snap.top_movers:
            out.append(f"  {m['symbol']} ({m['asset_class']}): score {m['score']:+.3f}")
        out.append("")
    for sleeve, data in snap.sleeves.items():
        out.append(f"SLEEVE {sleeve.upper()}:")
        out.append("  Top longs: " + ", ".join(
            f"{p['symbol']} ({p['score']:+.3f})" for p in data["longs"]
        ))
        out.append("  Top shorts: " + ", ".join(
            f"{p['symbol']} ({p['score']:+.3f})" for p in data["shorts"]
        ))
        out.append("")
    if snap.smart_money_recent:
        out.append("SMART-MONEY DISCLOSURES (last 24h):")
        for s in snap.smart_money_recent:
            amt = f"${s['amount']/1e6:.1f}M" if s["amount"] else "n/a"
            out.append(
                f"  [{s['date']}] {s['actor']} {s['side']} {s['ticker']} {amt} via {s['source']}"
            )
        out.append("")
    if snap.notable_headlines:
        out.append("HIGH-SENTIMENT HEADLINES (last 24h):")
        for h in snap.notable_headlines:
            sent = f"{h['sentiment']:+.2f}" if h["sentiment"] is not None else "n/a"
            out.append(
                f"  [{h['date']}] {h['symbol']} ({sent}) {h['publisher']}: {h['headline']}"
            )
        out.append("")
    return "\n".join(out)


def generate_summary(snap: Optional[DigestSnapshot] = None) -> Optional[str]:
    """Returns Claude-written 5-bullet summary, or None if AI is disabled
    or there's nothing to summarize."""
    if not claude.is_enabled():
        return None
    snap = snap or gather_snapshot()
    if not snap.top_movers and not snap.smart_money_recent and not snap.notable_headlines:
        return None
    block = _format_snapshot_for_claude(snap)
    user_prompt = (
        "Write the morning digest from this data — 5 short bullets, "
        "tickers + numbers, plain English, end with one caveat.\n\n" + block
    )
    return claude.ask(SYSTEM_PROMPT, user_prompt, max_tokens=700)


def render_html(summary: str, snap: DigestSnapshot, recipient_email: str) -> str:
    """Wrap the AI summary + a 'further reading' table in branded HTML.

    Inlined styles only — most email clients strip <style> blocks. Dark theme
    matches the app. Unsubscribe link points to /account where the toggle lives.
    """
    movers_rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #27272a;color:#e4e4e7;'>{m['symbol']}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #27272a;color:#a1a1aa;font-size:12px;'>{m['asset_class'].replace('_',' ')}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #27272a;text-align:right;color:{'#34d399' if m['score']>=0 else '#fb7185'};font-family:ui-monospace,monospace;'>{m['score']:+.3f}</td>"
        f"</tr>"
        for m in snap.top_movers[:8]
    ) or "<tr><td colspan='3' style='padding:6px 12px;color:#71717a;'>No movers in window.</td></tr>"

    summary_html = (
        summary.replace("\n\n", "</p><p style='margin:0 0 12px 0;'>")
               .replace("\n", "<br>")
    )

    return f"""\
<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#09090b;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#e4e4e7;">
  <div style="max-width:600px;margin:0 auto;padding:24px;">
    <div style="border-bottom:1px solid #27272a;padding-bottom:12px;margin-bottom:20px;">
      <h1 style="margin:0;font-size:22px;color:#fafafa;">EverNorthstar Daily ⭐</h1>
      <p style="margin:4px 0 0 0;font-size:12px;color:#71717a;">Honest signals. Smart money. Always pointing north.</p>
    </div>

    <div style="background:#18181b;border:1px solid #27272a;border-radius:8px;padding:16px 20px;margin-bottom:20px;">
      <p style="margin:0 0 12px 0;font-size:14px;line-height:1.6;">{summary_html}</p>
      <p style="margin:0;font-size:11px;color:#71717a;">AI-generated from overnight signals. Cross-check before trading.</p>
    </div>

    <h2 style="font-size:14px;color:#fafafa;margin:0 0 8px 0;">Top movers</h2>
    <table style="width:100%;border-collapse:collapse;background:#18181b;border:1px solid #27272a;border-radius:6px;overflow:hidden;">
      {movers_rows}
    </table>

    <div style="margin-top:24px;text-align:center;">
      <a href="https://evernorthstar.app" style="display:inline-block;background:#3b82f6;color:#ffffff;text-decoration:none;padding:10px 20px;border-radius:6px;font-size:13px;font-weight:500;">Open dashboard →</a>
    </div>

    <div style="margin-top:24px;padding-top:16px;border-top:1px solid #27272a;font-size:11px;color:#52525b;text-align:center;line-height:1.5;">
      Sent to {recipient_email}. This is not financial advice — past performance does not predict future results. <br>
      <a href="https://evernorthstar.app/account" style="color:#71717a;">Manage digest preferences →</a>
    </div>
  </div>
</body></html>"""


def render_plaintext(summary: str, snap: DigestSnapshot) -> str:
    """Plain-text fallback for clients that strip HTML."""
    lines = [
        "EverNorthstar Daily",
        "Honest signals. Smart money. Always pointing north.",
        "",
        summary,
        "",
        "Top movers:",
    ]
    for m in snap.top_movers[:8]:
        lines.append(
            f"  {m['symbol']:8} {m['asset_class']:14} {m['score']:+.3f}"
        )
    lines.extend([
        "",
        "Open dashboard: https://evernorthstar.app",
        "Manage digest preferences: https://evernorthstar.app/account",
    ])
    return "\n".join(lines)
