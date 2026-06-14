"""US Congress trade disclosures via FinancialModelingPrep.

FMP aggregates the official STOCK Act PTR filings from disclosures-clerk.house.gov
and efdsearch.senate.gov, parsing the PDFs and exposing them as JSON. Free tier
gives us 250 calls/day — plenty for a daily refresh.

Two endpoints used (the `/stable/` namespace — FMP's current API; the legacy
`/api/v4/senate-trading` paths still exist but aren't recommended):
  /stable/senate-latest?page=N&limit=100
  /stable/house-latest?page=N&limit=100

Both paginate ~100 trades per page, newest first. We pull pages until either we
hit `--pages` or we walk past `--lookback-days`.

Honest caveats encoded in the data:
  - Amounts are dollar *ranges* ("$15,001 - $50,000"); we store min + max,
    midpoint is what the composite signal uses.
  - 45-day legal lag — some filings come even later.
  - Some PTRs disclose at very different granularities; FMP normalizes, but the
    underlying records vary.
"""

from __future__ import annotations

import argparse
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Iterable

import httpx

from crypto_trends.config import settings
from crypto_trends.data.ingest.edgar import smart_money_id
from crypto_trends.data.store import connect

log = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/stable"

# Amount-range strings on House/Senate disclosures. Brackets fixed by the
# STOCK Act regulations — see https://disclosures-clerk.house.gov.
AMOUNT_BRACKETS: list[tuple[float, float, list[str]]] = [
    (1_001,        15_000,        ["$1,001", "$1 - $15,000"]),
    (15_001,       50_000,        ["$15,001"]),
    (50_001,       100_000,       ["$50,001"]),
    (100_001,      250_000,       ["$100,001"]),
    (250_001,      500_000,       ["$250,001"]),
    (500_001,      1_000_000,     ["$500,001"]),
    (1_000_001,    5_000_000,     ["$1,000,001"]),
    (5_000_001,    25_000_000,    ["$5,000,001"]),
    (25_000_001,   50_000_000,    ["$25,000,001"]),
    (50_000_001,   100_000_000,   ["$50,000,001"]),
]


def _parse_amount(text: str | None) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    s = text.strip()
    # Match against the canonical brackets first — cheaper than regex parsing.
    for lo, hi, prefixes in AMOUNT_BRACKETS:
        if any(s.startswith(p) for p in prefixes):
            return lo, hi
    # Fallback: pluck two numbers from the string ($X - $Y).
    nums = re.findall(r"\$?([\d,]+)", s)
    if len(nums) >= 2:
        try:
            return float(nums[0].replace(",", "")), float(nums[1].replace(",", ""))
        except ValueError:
            return None, None
    if len(nums) == 1:
        try:
            v = float(nums[0].replace(",", ""))
            return v, v
        except ValueError:
            return None, None
    return None, None


_NAME_NORMALIZE = re.compile(r"[^a-z0-9 ]+")


def _actor_id(chamber: str, member_name: str) -> tuple[str, str]:
    """Return (actor_id, normalized_display_name) from a raw member name.

    `chamber` ∈ {'house', 'senate'}. ID format: 'congress_<chamber>_<last>_<first>'.
    """
    name = (member_name or "").strip()
    # Strip honorifics (Hon., Mr., Mrs., Sen., Rep., etc.) and punctuation.
    name = re.sub(r"^(?:Hon\.?|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Sen\.?|Rep\.?)\s+",
                  "", name, flags=re.IGNORECASE)
    # Names usually come "First Middle Last" — but FMP sometimes uses "Last, First".
    if "," in name:
        last, _, rest = name.partition(",")
        parts = [last.strip()] + rest.strip().split()
        # Reorder to first-...-last so the rest of the pipeline is consistent.
        if len(parts) >= 2:
            parts = parts[1:] + [parts[0]]
    else:
        parts = name.split()

    parts = [_NAME_NORMALIZE.sub("", p.lower()) for p in parts if p.strip()]
    if not parts:
        return f"congress_{chamber}_unknown", name

    first = parts[0]
    last = parts[-1]
    return f"congress_{chamber}_{last}_{first}", " ".join(p.title() for p in parts)


def _side_from_type(txn_type: str | None) -> str:
    t = (txn_type or "").lower()
    if "purchase" in t or "buy" in t:
        return "buy"
    if "sale" in t or "sell" in t:
        return "sell"
    if "exchange" in t:
        return "exchange"
    return "buy"  # default to buy if FMP omits — rare


def _norm_ticker(t: str | None) -> str | None:
    if not t:
        return None
    s = t.strip().upper()
    # FMP occasionally includes class suffixes like "GOOG.L" — keep base only.
    s = re.sub(r"\..*$", "", s)
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", s):
        return None
    return s


class FreeTierExhausted(Exception):
    """Raised when FMP returns 402 — the free tier paywalled this request.

    On `senate-latest` / `house-latest` specifically, FMP free is limited to
    page=0 with limit≤25 (≈25 most-recent trades per chamber per call).
    """


def _fetch_page(client: httpx.Client, endpoint: str, page: int,
                limit: int = 25) -> list[dict]:
    """FMP free tier caps `limit` at 25 AND only allows page=0.

    Subsequent pages return 402 — we raise FreeTierExhausted so the caller
    can stop pagination cleanly without treating it as a hard failure.

    Auth via the `apikey:` HTTP header rather than query string — keeps the
    key out of URL-bearing logs (reverse proxies, WAFs, server access logs).
    """
    headers = {"apikey": settings.fmp_api_key}
    params = {"page": page, "limit": limit}
    r = client.get(f"{FMP_BASE}/{endpoint}", params=params, headers=headers,
                   timeout=30.0)
    if r.status_code == 401:
        raise RuntimeError(
            "FMP rejected the API key. Verify FMP_API_KEY in .env "
            "(or re-check the key at financialmodelingprep.com)."
        )
    if r.status_code == 402:
        raise FreeTierExhausted(f"{endpoint} page={page} requires paid tier")
    if r.status_code == 429:
        log.warning("FMP rate-limited; sleeping 15s")
        time.sleep(15)
        r = client.get(f"{FMP_BASE}/{endpoint}", params=params, headers=headers,
                       timeout=30.0)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def _ingest_endpoint(
    endpoint: str, chamber: str, pages: int, lookback_days: int,
) -> int:
    """Pull `pages` × ~100 trades from one endpoint, persist as smart_money rows."""
    cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).date().isoformat()

    rows: list[tuple] = []
    with httpx.Client() as client:
        for page in range(pages):
            try:
                trades = _fetch_page(client, endpoint, page)
            except FreeTierExhausted as e:
                log.info("[%s] %s — stopping pagination at page %d "
                         "(upgrade FMP for full history)", chamber, e, page)
                break
            log.info("[%s] page %d → %d trades", chamber, page, len(trades))
            if not trades:
                break

            page_oldest = None
            for t in trades:
                ticker = _norm_ticker(t.get("ticker") or t.get("symbol"))
                if not ticker:
                    continue
                # Different FMP endpoints use different field names; normalize.
                txn_date = (
                    t.get("transactionDate")
                    or t.get("transaction_date")
                    or t.get("date")
                )
                disc_date = (
                    t.get("disclosureDate")
                    or t.get("disclosure_date")
                    or txn_date
                )
                if not disc_date:
                    continue
                if disc_date < cutoff:
                    page_oldest = disc_date
                    continue

                # FMP returns firstName + lastName separately on the *latest*
                # endpoints; `office` is the combined alias. `owner` is the
                # *ownership type* (Self/Spouse/Joint), not the member's name.
                first = (t.get("firstName") or "").strip()
                last = (t.get("lastName") or "").strip()
                if first or last:
                    member = f"{first} {last}".strip()
                else:
                    member = (
                        t.get("office")
                        or t.get("representative")
                        or t.get("senator")
                        or t.get("memberName")
                        or ""
                    )
                ownership = (t.get("owner") or "").strip() or None
                actor_id, actor_name = _actor_id(chamber, member)
                side = _side_from_type(t.get("type") or t.get("transactionType"))
                amount_min, amount_max = _parse_amount(t.get("amount"))
                if amount_min is None:
                    # Without an amount we can't z-score anything; skip.
                    continue

                rid = smart_money_id(
                    f"congress_{chamber}", actor_id, ticker, txn_date,
                    disc_date, side, amount_min,
                )
                note_parts = []
                if t.get("district"):
                    note_parts.append(f"district={t['district']}")
                if ownership:
                    note_parts.append(f"owner={ownership}")
                if t.get("link") or t.get("ptr_link"):
                    note_parts.append("PTR linked")
                rows.append((
                    rid, f"congress_{chamber}", actor_id, actor_name,
                    "Representative" if chamber == "house" else "Senator",
                    None,   # party not in FMP free tier
                    ticker, side, txn_date, disc_date,
                    amount_min, amount_max, None,
                    " · ".join(note_parts) or None,
                ))

            # Early exit if the entire page is older than our cutoff.
            if page_oldest and page_oldest < cutoff and not any(
                ((t.get("disclosureDate") or t.get("disclosure_date") or "") >= cutoff)
                for t in trades
            ):
                log.info("[%s] page %d entirely older than cutoff — stopping", chamber, page)
                break
            time.sleep(0.4)  # gentle on FMP free tier

    if not rows:
        return 0

    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO smart_money_trades (id, source, actor_id, actor_name,
                actor_role, party_or_meta, ticker, side, transaction_date,
                disclosure_date, amount_min, amount_max, shares, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO NOTHING
            """, rows,
        )
    return len(rows)


def ingest_all(pages: int = 3, lookback_days: int = 180) -> int:
    if not settings.fmp_api_key:
        log.error(
            "FMP_API_KEY is not set. Add it to .env (free signup at "
            "financialmodelingprep.com) then re-run."
        )
        return 0

    total = 0
    for endpoint, chamber in (("senate-latest", "senate"),
                              ("house-latest", "house")):
        try:
            n = _ingest_endpoint(endpoint, chamber, pages, lookback_days)
            log.info("[%s] inserted %d new rows", chamber, n)
            total += n
        except Exception as e:
            log.exception("[%s] failed: %s", chamber, e)
    return total


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="Pull Congress trade disclosures via FMP.")
    p.add_argument("--pages", type=int, default=20,
                   help="Pages per endpoint (≈25 trades/page on FMP free tier).")
    p.add_argument("--lookback-days", type=int, default=180,
                   help="Skip trades disclosed before this many days ago.")
    args = p.parse_args()

    n = ingest_all(pages=args.pages, lookback_days=args.lookback_days)
    print(f"\nDone. {n} Congress trade rows inserted.")


if __name__ == "__main__":
    main()
