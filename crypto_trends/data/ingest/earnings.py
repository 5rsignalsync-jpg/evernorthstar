"""Earnings calendar via FMP /stable/earnings-calendar.

Free tier returns ~80 upcoming + historical announcements per call. We persist
the lot and filter to upcoming-only at query time. The dashboard surfaces
upcoming earnings as a row-level warning badge so users don't go long into a
guidance cut.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta

import httpx

from crypto_trends.config import settings
from crypto_trends.data.store import connect

log = logging.getLogger(__name__)

ENDPOINT = "https://financialmodelingprep.com/stable/earnings-calendar"


def _to_date(s: str | None) -> str | None:
    if not s:
        return None
    return s[:10]   # FMP returns YYYY-MM-DD already


def fetch_window(client: httpx.Client, from_: str, to: str) -> list[dict]:
    """FMP requires from/to params to return future earnings — the unparameterized
    call only returns recent historical data.

    Auth via the `apikey:` HTTP header (not query string) so the key doesn't
    leak into request logs / WAF logs / reverse proxy access logs.
    """
    if not settings.fmp_api_key:
        log.error("FMP_API_KEY not set — earnings calendar requires it")
        return []
    headers = {"apikey": settings.fmp_api_key}
    params = {"from": from_, "to": to}
    r = client.get(ENDPOINT, params=params, headers=headers, timeout=30.0)
    if r.status_code == 401:
        log.error("FMP rejected the API key for earnings-calendar")
        return []
    if r.status_code == 429:
        log.warning("FMP rate-limited; sleeping 15s")
        time.sleep(15)
        r = client.get(ENDPOINT, params=params, headers=headers, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def ingest(lookahead_days: int = 30, lookback_days: int = 14) -> int:
    today = datetime.utcnow().date()
    start = (today - timedelta(days=lookback_days)).isoformat()
    end = (today + timedelta(days=lookahead_days)).isoformat()
    with httpx.Client() as client:
        rows = fetch_window(client, start, end)
    log.info("FMP returned %d earnings records in window %s → %s",
             len(rows), start, end)

    payload: list[tuple] = []
    for row in rows:
        sym = (row.get("symbol") or "").upper().strip()
        date = _to_date(row.get("date"))
        if not sym or not date:
            continue
        payload.append((
            sym, date,
            _maybe_float(row.get("epsActual")),
            _maybe_float(row.get("epsEstimated")),
            _maybe_float(row.get("revenueActual")),
            _maybe_float(row.get("revenueEstimated")),
            row.get("lastUpdated"),
        ))

    if not payload:
        return 0

    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO earnings_calendar (symbol, date, eps_actual, eps_estimated,
                revenue_actual, revenue_estimated, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol, date) DO UPDATE SET
                eps_actual = excluded.eps_actual,
                eps_estimated = excluded.eps_estimated,
                revenue_actual = excluded.revenue_actual,
                revenue_estimated = excluded.revenue_estimated,
                last_updated = excluded.last_updated,
                fetched_at = now()
            """, payload,
        )
    log.info("earnings_calendar: inserted/updated %d rows", len(payload))
    return len(payload)


def upcoming_by_symbol(within_days: int = 14) -> dict[str, str]:
    """Return {ticker: ISO date} for announcements between today and `within_days`."""
    today = datetime.utcnow().date().isoformat()
    until = (datetime.utcnow().date() + timedelta(days=within_days)).isoformat()
    with connect(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT symbol, MIN(date) AS next_date
            FROM earnings_calendar
            WHERE date >= ? AND date <= ?
              AND eps_actual IS NULL    -- not yet reported
            GROUP BY symbol
            """, [today, until],
        ).fetchall()
    return {sym: str(d) for sym, d in rows}


def _maybe_float(x) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="Ingest FMP earnings calendar.")
    p.add_argument("--lookahead", type=int, default=30,
                   help="Days into the future to fetch (default 30).")
    p.add_argument("--lookback", type=int, default=14,
                   help="Days of past results to keep (default 14).")
    args = p.parse_args()
    n = ingest(lookahead_days=args.lookahead, lookback_days=args.lookback)
    print(f"\nDone. {n} earnings rows in DB.")


if __name__ == "__main__":
    main()
