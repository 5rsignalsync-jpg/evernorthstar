"""Fail-fast startup validators.

Run at FastAPI startup. Each check raises RuntimeError on a misconfiguration
that would silently compromise security or stability in production. Pre-empts
the worst class of "shipped to prod with dev defaults" failures.

Guarded by `settings.dev_mode` — local dev (DEV_MODE=true) skips all checks.
Production deploys MUST set DEV_MODE=false in env.
"""

from __future__ import annotations

import logging
import os

from crypto_trends.config import settings

log = logging.getLogger(__name__)

_DEV_SECRET_KEY = (
    "dev-only-change-me-in-production-fb8c2e9a7b3f4d5e6a8c9d0e1f2a3b4c"
)


def assert_production_ready() -> None:
    """Raise RuntimeError if any prod-only invariant is violated.

    Skipped entirely when DEV_MODE=true (the default for local dev).
    """
    if settings.dev_mode:
        log.info("dev mode enabled — skipping production safety checks")
        return

    failures: list[str] = []

    # C1 — refuse to ship with the in-source SECRET_KEY default.
    if settings.secret_key == _DEV_SECRET_KEY:
        failures.append(
            "SECRET_KEY is still the dev default. Set SECRET_KEY in env to a "
            "random 64+ character string before going live. Generate one with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(64))'"
        )
    elif len(settings.secret_key) < 32:
        failures.append(
            f"SECRET_KEY is only {len(settings.secret_key)} chars; use 32+ for "
            "production-grade JWT signing."
        )

    # C4 — SQLite + multi-worker uvicorn = corruption risk.
    workers_env = os.environ.get("UVICORN_WORKERS") or os.environ.get("WEB_CONCURRENCY")
    if workers_env:
        try:
            n = int(workers_env)
        except ValueError:
            n = 1
        if n > 1:
            failures.append(
                f"UVICORN_WORKERS/WEB_CONCURRENCY={n} but the auth/payments "
                "store uses SQLite with check_same_thread=False — concurrent "
                "writes will corrupt the DB. Either run with 1 worker, or "
                "migrate the user store to Postgres before scaling."
            )

    # Optional warnings (not fatal, just log loudly).
    if not settings.fmp_api_key:
        log.warning("FMP_API_KEY is empty — Congress + earnings ingest will skip")
    if not settings.stripe_secret_key:
        log.warning("STRIPE_SECRET_KEY is empty — billing endpoints will 503")
    if not settings.stripe_webhook_secret:
        log.warning("STRIPE_WEBHOOK_SECRET is empty — webhook handler will 503")

    if failures:
        msg = "Refusing to start. Production readiness failures:\n  - " + \
            "\n  - ".join(failures)
        log.error(msg)
        raise RuntimeError(msg)

    log.info("production safety checks passed")
