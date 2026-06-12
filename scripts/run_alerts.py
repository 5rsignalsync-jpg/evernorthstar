"""Scan all active alert rules and fire emails for any that trigger.

Runs hourly via GitHub Actions, immediately after refresh_all.py finishes.
Idempotent: rules have a 6h cooldown so re-running this script back-to-back
will not double-email.
"""

from __future__ import annotations

import logging
import sys

from crypto_trends.alerts import runner
from crypto_trends.auth.db import init_users_db

log = logging.getLogger("run_alerts")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


def main() -> int:
    init_users_db()
    summary = runner.run_alerts()
    log.info("alerts run complete: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
