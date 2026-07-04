"""Alert dispatcher.

Scans every enabled AlertRule against the latest DuckDB data and emails the
user when a rule's condition fires. Designed to be called immediately after
refresh_all.py (hourly), so users see triggers within ~1h of the data updating.

Cooldown: a rule won't re-fire within COOLDOWN_HOURS even if the condition
stays true — prevents spam when a stock hovers near a threshold.

Email is gated on RESEND_API_KEY. Without it, triggers still record an
AlertEvent (so the user sees history in the UI) but email_sent=False.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from crypto_trends.ai import email as email_mod
from crypto_trends.auth import db as auth_db
from crypto_trends.auth.models import AlertEvent, AlertRule, User
from crypto_trends.data.store import connect

log = logging.getLogger(__name__)

COOLDOWN_HOURS = 6


@dataclass
class TriggeredAlert:
    rule: AlertRule
    user_email: str
    observed_value: float
    summary: str


def _latest_score(symbol: str) -> Optional[float]:
    with connect(read_only=True) as conn:
        row = conn.execute(
            """
            SELECT score FROM signal_scores
            WHERE symbol = ? AND signal_name = 'momentum_v1'
            ORDER BY ts DESC LIMIT 1
            """,
            [symbol],
        ).fetchone()
        return float(row[0]) if row else None


def _latest_close(symbol: str) -> Optional[float]:
    with connect(read_only=True) as conn:
        row = conn.execute(
            """
            SELECT close FROM ohlcv
            WHERE symbol = ? ORDER BY ts DESC LIMIT 1
            """,
            [symbol],
        ).fetchone()
        return float(row[0]) if row else None


def _evaluate_rule(rule: AlertRule) -> Optional[float]:
    """Return the observed value if the rule SHOULD fire, else None."""
    if rule.condition in ("score_above", "score_below"):
        score = _latest_score(rule.symbol)
        if score is None:
            return None
        if rule.condition == "score_above" and score > rule.threshold:
            return score
        if rule.condition == "score_below" and score < rule.threshold:
            return score
        return None
    if rule.condition in ("price_above", "price_below"):
        price = _latest_close(rule.symbol)
        if price is None:
            return None
        if rule.condition == "price_above" and price > rule.threshold:
            return price
        if rule.condition == "price_below" and price < rule.threshold:
            return price
        return None
    if rule.condition == "zone_target":
        # Zone alerts: fire when the ticker's current extremum zone matches
        # the user-selected target. `observed_value` is the zone confidence
        # so we still return a numeric value for the AlertEvent record.
        if not rule.zone_target:
            return None
        try:
            from crypto_trends.portfolio.planning import (
                _load_price_and_score_history,
            )
            from crypto_trends.signals.extremum import compute_zone
        except Exception as e:
            log.warning("zone alert deps unavailable: %s", e)
            return None
        # Try both bare and USDT-suffixed variants for crypto tickers
        candidates = [rule.symbol]
        if not rule.symbol.endswith("USDT"):
            candidates.append(f"{rule.symbol}USDT")
        for sym in candidates:
            close, volume, scores = _load_price_and_score_history(
                sym, rule.symbol, days=365
            )
            if close.empty:
                continue
            reading = compute_zone(close, volume, scores)
            if reading.zone == rule.zone_target:
                return float(reading.zone_confidence)
            return None
        return None
    log.warning("unknown alert condition: %r", rule.condition)
    return None


def _format_email(rule: AlertRule, observed: float) -> tuple[str, str, str]:
    """Returns (subject, html, plain_text)."""
    op_words = {
        "score_above": "score crossed above",
        "score_below": "score dropped below",
        "price_above": "price crossed above",
        "price_below": "price dropped below",
        "zone_target": "entered zone",
    }
    op = op_words.get(rule.condition, rule.condition)
    is_price = rule.condition.startswith("price_")
    is_zone = rule.condition == "zone_target"
    if is_zone:
        threshold_str = (rule.zone_target or "").replace("_", " ")
        observed_str = f"{observed * 100:.0f}% confidence"
    else:
        threshold_str = f"${rule.threshold:.2f}" if is_price else f"{rule.threshold:+.3f}"
        observed_str = f"${observed:.2f}" if is_price else f"{observed:+.3f}"

    subject = f"🚨 {rule.symbol} {op} {threshold_str}"

    note_html = (
        f'<p style="margin:8px 0 0 0;font-size:12px;color:#a1a1aa;">'
        f'Your note: <em>{rule.note}</em></p>'
    ) if rule.note else ""

    html = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#09090b;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#e4e4e7;">
  <div style="max-width:520px;margin:0 auto;padding:24px;">
    <div style="background:#18181b;border:1px solid #f59e0b;border-radius:8px;padding:20px;">
      <p style="margin:0;font-size:11px;color:#fbbf24;text-transform:uppercase;letter-spacing:0.06em;">Alert triggered</p>
      <h2 style="margin:6px 0 12px 0;font-size:20px;color:#fafafa;">{rule.symbol} {op} {threshold_str}</h2>
      <p style="margin:0;font-size:14px;color:#d4d4d8;">Current {'price' if is_price else 'score'}: <strong>{observed_str}</strong></p>
      {note_html}
    </div>
    <div style="margin-top:16px;text-align:center;">
      <a href="https://evernorthstar.app" style="display:inline-block;background:#3b82f6;color:#ffffff;text-decoration:none;padding:10px 20px;border-radius:6px;font-size:13px;font-weight:500;">Open dashboard →</a>
    </div>
    <div style="margin-top:20px;padding-top:14px;border-top:1px solid #27272a;font-size:11px;color:#52525b;text-align:center;line-height:1.5;">
      Not financial advice. <a href="https://evernorthstar.app/account" style="color:#71717a;">Manage alerts →</a>
    </div>
  </div>
</body></html>"""

    text = (
        f"ALERT: {rule.symbol} {op} {threshold_str}\n"
        f"Current {'price' if is_price else 'score'}: {observed_str}\n"
        + (f"Your note: {rule.note}\n" if rule.note else "")
        + "\nOpen: https://evernorthstar.app\n"
        "Manage: https://evernorthstar.app/account"
    )
    return subject, html, text


def run_alerts() -> dict:
    """Scan all enabled rules, fire emails for those that trigger.

    Returns a dict with counts: {scanned, triggered, emails_sent, cooled_down}.
    """
    cutoff = datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS)
    scanned = 0
    triggered = 0
    emails_sent = 0
    cooled_down = 0

    with Session(auth_db._engine) as session:
        rules = session.exec(
            select(AlertRule).where(AlertRule.enabled == True)  # noqa: E712
        ).all()
        scanned = len(rules)

        for rule in rules:
            observed = _evaluate_rule(rule)
            if observed is None:
                continue
            if rule.last_triggered_at and rule.last_triggered_at > cutoff:
                cooled_down += 1
                continue

            triggered += 1
            user = session.get(User, rule.user_id)
            email_to = user.email if user else None

            sent = False
            if email_to and email_mod.is_enabled():
                subject, html, text = _format_email(rule, observed)
                sent = email_mod.send(
                    to=email_to, subject=subject, html=html, text=text
                )
                if sent:
                    emails_sent += 1

            session.add(AlertEvent(
                rule_id=rule.id or 0,
                user_id=rule.user_id,
                observed_value=observed,
                email_sent=sent,
            ))
            rule.last_triggered_at = datetime.utcnow().replace(tzinfo=None)
            session.add(rule)

        session.commit()

    log.info(
        "alerts: scanned=%d triggered=%d emails_sent=%d cooled_down=%d",
        scanned, triggered, emails_sent, cooled_down,
    )
    return {
        "scanned": scanned,
        "triggered": triggered,
        "emails_sent": emails_sent,
        "cooled_down": cooled_down,
    }
