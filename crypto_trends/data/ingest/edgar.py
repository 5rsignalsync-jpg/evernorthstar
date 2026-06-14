"""SEC EDGAR ingestion for 13F filings + insider Form 4 trades.

EDGAR is the SEC's free public filings system. No auth required, but they
require a User-Agent that identifies the caller (we use the env var or a default
contact string).

This module covers:
  - 13F-HR filings for curated institutional investors (Berkshire, Pershing, etc.).
    We pull the latest 13F's information_table.xml, parse holdings, and persist as
    `smart_money_trades` rows (one row per holding) with side='buy' since 13F is
    long-only.
  - Form 4 filings for tickers in our equity universe. Form 4 is filed within 2
    business days of insider trades, so this is our freshest "smart money" signal.

Caveats encoded honestly:
  - 13F has a 45-day lag from quarter-end.
  - 13F is long-only equity book; no shorts, derivatives, or foreign holdings.
  - Form 4 sales include 10b5-1 programmed sales; we keep a flag where available.
  - Issuer matching uses CUSIP for 13F (we maintain a small CUSIP→ticker map for
    the universe) and CIK for Form 4 (cleaner).
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from xml.etree import ElementTree as ET

import httpx

from crypto_trends.data.store import connect

log = logging.getLogger(__name__)

EDGAR_BASE = "https://www.sec.gov"
SUBMISSIONS_BASE = "https://data.sec.gov/submissions"
USER_AGENT = "crypto-trends contact@example.com"   # SEC asks for an identifying UA

# Curated 13F filers we track. Add or remove freely; the rest of the pipeline
# adapts. CIKs from https://www.sec.gov/cgi-bin/browse-edgar.
TRACKED_FUNDS: dict[str, dict] = {
    "0001067983": {"name": "Berkshire Hathaway",           "manager": "Warren Buffett"},
    "0001350694": {"name": "Bridgewater Associates",       "manager": "Bridgewater"},
    "0001037389": {"name": "Renaissance Technologies",     "manager": "Renaissance"},
    "0001336528": {"name": "Pershing Square Capital",      "manager": "Bill Ackman"},
    "0001029160": {"name": "Soros Fund Management",        "manager": "Soros Fund"},
    "0001364742": {"name": "BlackRock Inc",                "manager": "BlackRock"},
    "0001423053": {"name": "Citadel Advisors",             "manager": "Ken Griffin"},
    "0001167483": {"name": "Tudor Investment Corp",        "manager": "Paul Tudor Jones"},
    "0001656456": {"name": "Scion Asset Management",       "manager": "Michael Burry"},
    "0001603466": {"name": "ARK Investment Mgmt",          "manager": "Cathie Wood"},
}


# ---------- HTTP helpers ------------------------------------------------------

def _client() -> httpx.Client:
    """SEC asks for an identifying User-Agent and rate-limits to ~10 req/sec.

    We're conservative and serialize at the call sites; this client is just
    used as the per-process pool with the right headers.
    """
    return httpx.Client(
        timeout=30.0,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
    )


def _gentle_sleep() -> None:
    """SEC's fair-use limit is ~10 req/sec; we stay well under at ~5/sec."""
    time.sleep(0.2)


def _get_json(client: httpx.Client, url: str) -> dict:
    r = client.get(url)
    r.raise_for_status()
    return r.json()


def _get_text(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


# ---------- Universe lookup (issuer matching) ---------------------------------

def _load_universe_match() -> tuple[dict[str, str], dict[str, str]]:
    """Return (cik_to_ticker, name_normalized_to_ticker).

    `cik_to_ticker` covers SEC-registered companies (for Form 4 matching).
    `name_normalized_to_ticker` is a fallback for 13F (CUSIP licensing prevents
    a free CUSIP→ticker map, so we approximate by company name).
    """
    with connect(read_only=True) as conn:
        symbols = [r[0] for r in conn.execute(
            "SELECT symbol FROM universe WHERE asset_class IN "
            "('equity_large', 'equity_micro') AND included"
        ).fetchall()]

    # SEC's authoritative ticker → CIK map.
    with _client() as client:
        company_tickers = _get_json(
            client, "https://www.sec.gov/files/company_tickers.json")

    cik_by_ticker: dict[str, str] = {}
    ticker_by_cik: dict[str, str] = {}
    name_by_ticker: dict[str, str] = {}

    for entry in company_tickers.values():
        ticker = entry["ticker"].upper()
        if ticker not in symbols:
            continue
        cik = str(entry["cik_str"]).zfill(10)
        cik_by_ticker[ticker] = cik
        ticker_by_cik[cik] = ticker
        name_by_ticker[ticker] = entry["title"]

    name_to_ticker: dict[str, str] = {}
    for t, name in name_by_ticker.items():
        name_to_ticker[_normalize_name(name)] = t

    log.info("universe matcher: %d symbols mapped to CIKs", len(cik_by_ticker))
    return ticker_by_cik, name_to_ticker


_CORP_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|llc|holdings|"
    r"group|class\s+[abc]|com|common\s+stock|common|cl\s+[abc])\b",
    re.IGNORECASE,
)
_NONALNUM = re.compile(r"[^a-z0-9 ]+")


def _normalize_name(name: str) -> str:
    s = (name or "").lower()
    s = _CORP_SUFFIXES.sub(" ", s)
    s = _NONALNUM.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# ---------- ID derivation -----------------------------------------------------

def smart_money_id(
    source: str, actor_id: str, ticker: str,
    transaction_date: str | None, disclosure_date: str, side: str,
    amount_min: float | None,
) -> int:
    """Deterministic primary key. Same row content → same id → ON CONFLICT no-op."""
    key = "|".join([
        source, actor_id, ticker,
        str(transaction_date or ""), str(disclosure_date),
        side, str(amount_min or 0.0),
    ])
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    # 15 hex chars = 60 bits, safely within BIGINT.
    return int(digest[:15], 16)


# ---------- 13F ingestion -----------------------------------------------------

@dataclass(frozen=True)
class Holding:
    ticker: str
    issuer_name: str
    cusip: str
    value_usd: float
    shares: float


def _latest_13f_accession(client: httpx.Client, cik: str) -> tuple[str, str] | None:
    """Return (accession_no_dashes, filed_date_iso) for the most recent 13F-HR."""
    data = _get_json(client, f"{SUBMISSIONS_BASE}/CIK{cik}.json")
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])

    for i, form in enumerate(forms):
        if form.startswith("13F-HR"):
            return accessions[i].replace("-", ""), dates[i]
    return None


def _find_information_table(client: httpx.Client, cik: str, accession: str) -> str | None:
    """Locate the information table XML inside the 13F filing's directory.

    Filers use arbitrary filenames (often a random numeric stem like "53405.xml"),
    so we list all XMLs, skip the wrapper `primary_doc.xml`, and pick whichever
    body contains the `<infoTable>` root.
    """
    idx_url = f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/{accession}/"
    try:
        json_index = _get_json(client, idx_url + "index.json")
    except httpx.HTTPError:
        return None

    xml_files = [
        item["name"] for item in json_index.get("directory", {}).get("item", [])
        if item.get("name", "").endswith(".xml")
        and item["name"].lower() != "primary_doc.xml"
    ]
    if not xml_files:
        return None

    # If only one XML besides primary_doc, take it without HEAD-fetching.
    if len(xml_files) == 1:
        return idx_url + xml_files[0]

    for name in xml_files:
        _gentle_sleep()
        try:
            sample = _get_text(client, idx_url + name)
        except httpx.HTTPError:
            continue
        # `<infoTable>` is the row element; `<informationTable>` is the container.
        if "<infoTable" in sample or "<informationTable" in sample:
            return idx_url + name
    return None


def _parse_13f_xml(xml_text: str) -> list[Holding]:
    """Parse 13F informationTable.xml into Holdings.

    13F XML uses a namespace; we strip it for simpler XPath.
    """
    # Strip namespace declarations to simplify parsing.
    xml_text = re.sub(r'\sxmlns="[^"]+"', "", xml_text, count=1)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.warning("13F XML parse failed: %s", e)
        return []

    out: list[Holding] = []
    for info in root.findall(".//infoTable"):
        name = (info.findtext("nameOfIssuer") or "").strip()
        cusip = (info.findtext("cusip") or "").strip()
        value_raw = info.findtext("value")
        shares_raw = info.findtext("shrsOrPrnAmt/sshPrnamt")
        put_call = (info.findtext("putCall") or "").strip()
        if put_call:                       # skip options legs
            continue
        try:
            value = float(value_raw or 0)
            shares = float(shares_raw or 0)
        except ValueError:
            continue
        # SEC raised reporting precision in 2022; treat values as full dollars
        # if they're large enough to be plausible, else interpret as thousands.
        if value > 0 and value < 1e7:
            value *= 1000
        out.append(Holding(ticker="", issuer_name=name, cusip=cusip,
                           value_usd=value, shares=shares))
    return out


def ingest_13f_for_fund(cik: str, meta: dict, name_to_ticker: dict[str, str]) -> int:
    cik = cik.zfill(10)
    with _client() as client:
        latest = _latest_13f_accession(client, cik)
        if not latest:
            log.warning("no 13F-HR for CIK=%s (%s)", cik, meta["name"])
            return 0
        accession, filed_date = latest
        _gentle_sleep()

        info_table_url = _find_information_table(client, cik, accession)
        if not info_table_url:
            log.warning("13F infotable not found for %s (cik=%s, acc=%s)",
                        meta["name"], cik, accession)
            return 0
        _gentle_sleep()
        try:
            xml_text = _get_text(client, info_table_url)
        except httpx.HTTPError as e:
            log.warning("13F infotable fetch failed for %s: %s", meta["name"], e)
            return 0

    holdings = _parse_13f_xml(xml_text)
    log.info("%s: parsed %d holdings from 13F filed %s",
             meta["name"], len(holdings), filed_date)

    actor_id = f"cik_{cik}"
    actor_name = meta["name"]
    actor_role = "Hedge Fund"
    rows: list[tuple] = []
    matched = 0
    for h in holdings:
        norm = _normalize_name(h.issuer_name)
        ticker = name_to_ticker.get(norm)
        if not ticker:
            # try a looser match — first word + last word
            words = norm.split()
            if len(words) >= 2:
                short = " ".join([words[0], words[-1]])
                ticker = name_to_ticker.get(short)
        if not ticker:
            continue
        matched += 1
        rid = smart_money_id(
            "13f", actor_id, ticker, None, filed_date, "buy", h.value_usd)
        rows.append((
            rid, "13f", actor_id, actor_name, actor_role, "fund",
            ticker, "buy", None, filed_date, h.value_usd, h.value_usd,
            h.shares, f"latest 13F-HR (long-only book)",
        ))

    log.info("%s: %d/%d holdings matched to our universe",
             meta["name"], matched, len(holdings))

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


def ingest_13f_all() -> int:
    _ticker_by_cik, name_to_ticker = _load_universe_match()
    total = 0
    for cik, meta in TRACKED_FUNDS.items():
        try:
            total += ingest_13f_for_fund(cik, meta, name_to_ticker)
        except Exception as e:
            log.exception("13F ingest failed for %s: %s", meta["name"], e)
    return total


# ---------- Form 4 ingestion --------------------------------------------------

def _list_form4_for_cik(client: httpx.Client, cik: str, lookback_days: int) -> list[dict]:
    data = _get_json(client, f"{SUBMISSIONS_BASE}/CIK{cik}.json")
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])

    cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).date().isoformat()
    out = []
    for i, form in enumerate(forms):
        if form != "4":
            continue
        if dates[i] < cutoff:
            break    # results are sorted newest-first
        out.append({
            "accession_clean": accessions[i].replace("-", ""),
            "accession_raw": accessions[i],
            "filed": dates[i],
            "primary_doc": primary_docs[i],
        })
    return out


def _parse_form4(xml_text: str) -> tuple[str, str, bool, list[dict]]:
    """Return (insider_name, role_flags, is_10b5_1, [{side, shares, price, date, code}]).

    Form 4 XML has both `nonDerivativeTransaction` and `derivativeTransaction`;
    we extract non-derivative only for the MVP (cleaner buy/sell signal). The
    `<aff10b5One>` element at the filing level — when present and "true" —
    marks the whole filing as part of a programmed plan.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.debug("form 4 parse failed: %s", e)
        return "", "", False, []

    insider = ""
    rep = root.find(".//reportingOwner/reportingOwnerId/rptOwnerName")
    if rep is not None and rep.text:
        insider = rep.text.strip()

    role_flags: list[str] = []
    rel = root.find(".//reportingOwner/reportingOwnerRelationship")
    if rel is not None:
        for child in rel:
            val = (child.text or "").strip().lower()
            if val in ("1", "true"):
                role_flags.append(child.tag.replace("is", ""))

    is_10b5_1 = False
    aff = root.find(".//aff10b5One")
    if aff is not None and (aff.text or "").strip().lower() in ("1", "true"):
        is_10b5_1 = True

    transactions: list[dict] = []
    for txn in root.findall(".//nonDerivativeTransaction"):
        code = txn.findtext(".//transactionCoding/transactionCode") or ""
        date = txn.findtext(".//transactionDate/value") or ""
        shares = txn.findtext(".//transactionAmounts/transactionShares/value") or "0"
        price = txn.findtext(".//transactionAmounts/transactionPricePerShare/value") or "0"
        acq_disp = txn.findtext(
            ".//transactionAmounts/transactionAcquiredDisposedCode/value") or ""
        try:
            shares_f = float(shares)
            price_f = float(price)
        except ValueError:
            continue
        side = "buy" if acq_disp == "A" else "sell" if acq_disp == "D" else "exchange"
        transactions.append({
            "date": date, "side": side, "shares": shares_f, "price": price_f,
            "code": code,
        })
    return insider, ",".join(role_flags), is_10b5_1, transactions


def ingest_form4_for_universe(lookback_days: int = 30) -> int:
    ticker_by_cik, _ = _load_universe_match()
    rows: list[tuple] = []
    total_filings = 0

    with _client() as client:
        for cik, ticker in ticker_by_cik.items():
            try:
                filings = _list_form4_for_cik(client, cik, lookback_days)
            except httpx.HTTPError as e:
                log.warning("form 4 list failed for %s (%s): %s", ticker, cik, e)
                continue
            _gentle_sleep()
            if not filings:
                continue
            total_filings += len(filings)
            for f in filings:
                # `primaryDocument` is often the XSL-wrapped HTML view
                # (xslF345X06/form4.xml) — we want the raw XML alongside it.
                doc_name = f["primary_doc"]
                if "/" in doc_name:
                    doc_name = doc_name.split("/")[-1]
                doc_url = (f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/"
                           f"{f['accession_clean']}/{doc_name}")
                try:
                    xml_text = _get_text(client, doc_url)
                except httpx.HTTPError as e:
                    log.debug("form 4 doc fetch failed: %s", e)
                    continue
                _gentle_sleep()
                insider, roles, is_10b5_1, txns = _parse_form4(xml_text)
                if not insider or not txns:
                    continue
                for t in txns:
                    rid = smart_money_id(
                        "insider", insider, ticker, t["date"], f["filed"],
                        t["side"], t["shares"] * t["price"])
                    amount = t["shares"] * t["price"]
                    note = f"code={t['code']}"
                    if is_10b5_1:
                        note += " (10b5-1)"
                    rows.append((
                        rid, "insider", f"insider_{insider.replace(' ', '_').lower()}",
                        insider, "Insider", roles or None,
                        ticker, t["side"], t["date"], f["filed"],
                        amount, amount, t["shares"], note,
                    ))

    log.info("form 4 ingest: %d filings, %d transaction rows ready",
             total_filings, len(rows))

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


def main() -> None:
    from crypto_trends.logging_config import configure
    configure()

    p = argparse.ArgumentParser(description="SEC EDGAR ingestion: 13F + Form 4.")
    p.add_argument("--source", default="all", choices=["all", "13f", "form4"])
    p.add_argument("--lookback-days", type=int, default=30,
                   help="For Form 4 only.")
    args = p.parse_args()

    total = 0
    if args.source in ("all", "13f"):
        log.info("─── 13F ingestion ───")
        total += ingest_13f_all()
    if args.source in ("all", "form4"):
        log.info("─── Form 4 ingestion ───")
        total += ingest_form4_for_universe(lookback_days=args.lookback_days)
    print(f"\nDone. {total} smart-money rows inserted/updated.")


if __name__ == "__main__":
    main()
