"""Full data + signal refresh pipeline.

Designed for cron / scheduled invocation. Each phase is isolated — a failure
in one (e.g. yfinance times out) is logged but doesn't abort later phases.
Exit code reflects whether *any* phase failed.

Usage:
    python -m scripts.refresh_all                  # default daily refresh
    python -m scripts.refresh_all --penny-screen   # also re-run penny screener (slow)
    python -m scripts.refresh_all --skip-crypto    # skip a specific phase
    python -m scripts.refresh_all --crypto-only    # ONLY crypto phases (for 15-min intraday cron)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from crypto_trends.logging_config import configure


@dataclass
class PhaseResult:
    name: str
    ok: bool
    duration_s: float
    error: str | None = None
    rows: int | None = None


def _run_phase(name: str, func) -> PhaseResult:
    log = logging.getLogger("refresh_all")
    log.info("─── phase: %s ───", name)
    started = time.monotonic()
    try:
        rows = func()
        elapsed = time.monotonic() - started
        log.info("✓ %s done in %.1fs (rows=%s)", name, elapsed, rows)
        return PhaseResult(name=name, ok=True, duration_s=elapsed, rows=rows)
    except Exception as e:
        elapsed = time.monotonic() - started
        log.exception("✗ %s failed in %.1fs", name, elapsed)
        return PhaseResult(name=name, ok=False, duration_s=elapsed, error=str(e))


def main() -> int:
    configure()
    log = logging.getLogger("refresh_all")

    p = argparse.ArgumentParser(description="Full pipeline refresh.")
    p.add_argument("--skip-crypto", action="store_true")
    p.add_argument("--skip-equities", action="store_true")
    p.add_argument("--skip-fundamentals", action="store_true")
    p.add_argument("--skip-news", action="store_true")
    p.add_argument("--skip-signals", action="store_true")
    p.add_argument("--skip-congress", action="store_true",
                   help="Skip the Congress (FMP) phase even if FMP_API_KEY is set.")
    p.add_argument("--skip-earnings", action="store_true",
                   help="Skip the earnings-calendar (FMP) phase.")
    p.add_argument("--congress-lookback-days", type=int, default=180)
    p.add_argument("--penny-screen", action="store_true",
                   help="Re-run the live penny-stock screener (~3-10 min). "
                        "Otherwise reuses the hardcoded candidate list.")
    p.add_argument("--crypto-since", default="30d")
    p.add_argument("--equity-since", default="365d")
    p.add_argument("--crypto-only", action="store_true",
                   help="Only run crypto + crypto_micro phases (skip everything else). "
                        "Used by the 15-min intraday cron. Signals restricted to crypto sleeves.")
    args = p.parse_args()

    # --crypto-only implies skip-everything-else + a shorter default window.
    # Intraday refresh doesn't need 30 days of history, just enough to compute
    # the current bar's momentum score. Keeping it short (~2d) means Binance
    # returns fewer bars per symbol and the whole run stays under ~90s.
    if args.crypto_only:
        args.skip_equities = True
        args.skip_fundamentals = True
        args.skip_news = True
        args.skip_congress = True
        args.skip_earnings = True
        if args.crypto_since == "30d":
            args.crypto_since = "2d"

    results: list[PhaseResult] = []

    # 1) Crypto OHLCV — majors (utility-focused, memes excluded)
    if not args.skip_crypto:
        def _crypto():
            from crypto_trends.data.ingest.prices import ingest
            ingest(since=args.crypto_since, size=50)
            return None
        results.append(_run_phase("crypto_ohlcv", _crypto))

    # 1b) Crypto Micro OHLCV — memes + small alts (moonshot sleeve).
    # Without this phase, crypto_micro signals go stale silently while majors
    # stay fresh. Bug surfaced in 6/9 smoke test where crypto_micro was 8 days behind.
    if not args.skip_crypto:
        def _crypto_micro():
            from crypto_trends.data.ingest.prices import ingest
            ingest(since=args.crypto_since, size=30, rank_start=30,
                   asset_class="crypto_micro")
            return None
        results.append(_run_phase("crypto_micro_ohlcv", _crypto_micro))

    # 2) Equity OHLCV
    if not args.skip_equities:
        def _equities():
            from crypto_trends.data.ingest.equities import (
                _parse_since, _utc_now, ingest_large, ingest_penny,
            )
            start = _parse_since(args.equity_since)
            end = _utc_now()
            n = ingest_large(start, end)
            candidates = None
            if args.penny_screen:
                from crypto_trends.data.screener import screen_penny_stocks
                candidates = screen_penny_stocks()
            n += ingest_penny(start, end, candidates=candidates)
            return n
        results.append(_run_phase("equity_ohlcv", _equities))

    # 3) Fundamentals
    if not args.skip_fundamentals:
        def _funds():
            from crypto_trends.data.ingest.fundamentals import ingest_for_asset_class
            return ingest_for_asset_class("equity_large")
        results.append(_run_phase("fundamentals", _funds))

    # 4) News (FinBERT-scored)
    if not args.skip_news:
        def _news():
            from crypto_trends.data.ingest.news import ingest_crypto, ingest_equities
            n = ingest_equities() + ingest_crypto()
            return n
        results.append(_run_phase("news", _news))

    # 4b) Congress (gated on FMP_API_KEY in .env)
    if not args.skip_congress:
        def _congress():
            from crypto_trends.config import settings
            if not settings.fmp_api_key:
                log.info("FMP_API_KEY not set — skipping Congress phase")
                return 0
            from crypto_trends.data.ingest.congress import ingest_all
            return ingest_all(pages=3, lookback_days=args.congress_lookback_days)
        results.append(_run_phase("congress", _congress))

    # 4c) Earnings calendar (also gated on FMP_API_KEY)
    if not args.skip_earnings:
        def _earnings():
            from crypto_trends.config import settings
            if not settings.fmp_api_key:
                log.info("FMP_API_KEY not set — skipping earnings phase")
                return 0
            from crypto_trends.data.ingest.earnings import ingest
            return ingest(lookahead_days=30, lookback_days=14)
        results.append(_run_phase("earnings", _earnings))

    # 5) Signals (all asset classes, all signals — or just crypto if --crypto-only)
    if not args.skip_signals:
        def _signals():
            from crypto_trends.signals.runner import (
                compute_and_store_long_term, compute_and_store_momentum,
            )
            asset_classes = (
                ("crypto", "crypto_micro")
                if args.crypto_only
                else ("crypto", "crypto_micro", "equity_large", "equity_micro")
            )
            total = 0
            for ac in asset_classes:
                total += compute_and_store_momentum(asset_class=ac, latest_only=True)
            if not args.crypto_only:
                total += compute_and_store_long_term("equity_large")
            return total
        results.append(_run_phase("signals", _signals))

    # Summary
    log.info("─── summary ───")
    any_failed = False
    for r in results:
        status = "OK" if r.ok else "FAIL"
        rows_str = f"rows={r.rows}" if r.rows is not None else ""
        err = f" — {r.error}" if r.error else ""
        log.info("  %-15s %-4s %6.1fs %s%s", r.name, status, r.duration_s, rows_str, err)
        if not r.ok:
            any_failed = True

    total_time = sum(r.duration_s for r in results)
    log.info("total: %.1fs across %d phases (failures=%d)",
             total_time, len(results), sum(1 for r in results if not r.ok))

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
