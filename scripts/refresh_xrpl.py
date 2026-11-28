"""CLI runner for XRPL metrics refresh.

Usage:
    python -m scripts.refresh_xrpl

Called by the APScheduler job in crypto_trends.scheduler (every 6h) and
available as a one-off script for local testing or an ad-hoc refresh.
"""

from __future__ import annotations

import logging
import sys

from crypto_trends.data.ingest.xrpl import refresh_all
from crypto_trends.data.store import init_db


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Idempotent — brings xrpl_metrics (and any newer DuckDB tables) into
    # existence on a machine that was deployed before the schema change.
    init_db()
    outcomes = refresh_all()
    for key, status in outcomes.items():
        print(f"  {key}: {status}")
    # Exit non-zero only if *everything* failed — one missing metric
    # should not fail the scheduled job (schedule-of-last-resort stays live).
    if outcomes and all(v == "skipped" for v in outcomes.values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
