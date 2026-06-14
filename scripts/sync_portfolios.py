"""Sync all active brokerage accounts via Plaid.

Runs once daily via GitHub Actions. Plaid holdings update T+1 so an
hourly sync is wasteful; daily matches the brokerage cadence.

Without PLAID_CLIENT_ID + PLAID_SECRET set, this exits 0 with a 'feature
pending' log line.
"""

from __future__ import annotations

import logging
import sys

from crypto_trends.auth.db import init_users_db
from crypto_trends.portfolio import sync

log = logging.getLogger("sync_portfolios")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


def main() -> int:
    init_users_db()
    summary = sync.sync_all_active_accounts()
    log.info("portfolio sync complete: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
