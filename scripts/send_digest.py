"""Send the morning AI digest to all opted-in users.

Run from a cron (GitHub Actions or systemd) once daily, ~12:00 UTC (~7am ET).

Behavior:
  - Builds the digest snapshot ONCE (DuckDB read), generates the summary ONCE
    via Claude, then mails the same body to every opted-in user. Personalization
    today is the recipient email in the footer; per-user watchlist personalization
    is a future enhancement.
  - Skips users who received a digest in the last 18h (re-run protection).
  - Logs structured outcome counts so cron alerts are informative.
  - Exits 0 even on partial failure — one bad address shouldn't fail the job.

Required env on Fly: ANTHROPIC_API_KEY, RESEND_API_KEY.
Without either, the job logs a clear 'feature pending' line and exits clean.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from crypto_trends.ai import claude, digest, email
from crypto_trends.auth.db import _engine, init_users_db
from crypto_trends.auth.models import User

log = logging.getLogger("send_digest")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


def main() -> int:
    init_users_db()

    if not claude.is_enabled():
        log.warning("ANTHROPIC_API_KEY not set — digest summary generation disabled. Skipping job.")
        return 0
    if not email.is_enabled():
        log.warning("RESEND_API_KEY not set — outbound email disabled. Skipping job.")
        return 0

    snap = digest.gather_snapshot()
    summary = digest.generate_summary(snap)
    if not summary:
        log.warning("Claude returned no summary (data too thin?). Skipping send.")
        return 0

    cutoff = datetime.utcnow() - timedelta(hours=18)
    sent_count = 0
    skipped_count = 0
    failed_count = 0

    with Session(_engine) as session:
        # Only opted-in. Skip if recently sent (rerun protection).
        stmt = select(User).where(User.daily_digest_opt_in == True)  # noqa: E712
        users = session.exec(stmt).all()
        log.info("digest: %d opted-in users", len(users))

        for user in users:
            if user.daily_digest_last_sent_at and user.daily_digest_last_sent_at > cutoff:
                skipped_count += 1
                continue

            html = digest.render_html(summary, snap, user.email)
            text = digest.render_plaintext(summary, snap)
            subject = f"EverNorthstar Daily · {datetime.utcnow():%b %d}"

            ok = email.send(to=user.email, subject=subject, html=html, text=text)
            if ok:
                user.daily_digest_last_sent_at = datetime.utcnow().replace(tzinfo=None)
                session.add(user)
                sent_count += 1
            else:
                failed_count += 1
        session.commit()

    log.info(
        "digest done: sent=%d skipped_recent=%d failed=%d",
        sent_count, skipped_count, failed_count,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
