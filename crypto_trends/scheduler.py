"""In-process scheduler for the intraday crypto refresh.

Runs inside the FastAPI primary machine so the refresh writes to the same
DuckDB file the API reads. This replaces the GHA cron that was queueing 30-90
min behind schedule on the free tier; running here means the schedule is
deterministic (APScheduler fires on wall-clock time, no shared queue).

Architecture tradeoff: requires `min_machines_running = 1` in fly.toml so the
machine never auto-stops. The scheduler can't fire from a stopped machine.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_intraday_crypto_refresh() -> None:
    """Run crypto-only refresh then alerts scan. Mirrors the old GHA steps."""
    started = datetime.utcnow()
    log.info("intraday_crypto: start ts=%s", started.isoformat())

    for step, args in (
        ("refresh_all", [sys.executable, "-m", "scripts.refresh_all", "--crypto-only"]),
        ("run_alerts", [sys.executable, "-m", "scripts.run_alerts"]),
    ):
        step_started = datetime.utcnow()
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        duration = (datetime.utcnow() - step_started).total_seconds()
        tail = (stdout or b"").decode("utf-8", errors="replace")[-2000:]
        if proc.returncode == 0:
            log.info(
                "intraday_crypto: step=%s ok duration_s=%.1f\n%s",
                step, duration, tail,
            )
        else:
            log.error(
                "intraday_crypto: step=%s FAILED rc=%d duration_s=%.1f\n%s",
                step, proc.returncode, duration, tail,
            )
            return  # don't run alerts if refresh failed

    total = (datetime.utcnow() - started).total_seconds()
    log.info("intraday_crypto: done total_duration_s=%.1f", total)


async def _run_xrpl_refresh() -> None:
    """Refresh the /xrpl tracker's metrics (amendments, RLUSD, ETF, RWA).

    Separate from intraday_crypto because:
      - source rate limits are different (CoinGecko, SoSoValue)
      - every 6h is plenty — adoption metrics don't move intraday
      - failure here must not block price-driven alerts
    """
    started = datetime.utcnow()
    log.info("xrpl_refresh: start ts=%s", started.isoformat())
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "scripts.refresh_xrpl",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    duration = (datetime.utcnow() - started).total_seconds()
    tail = (stdout or b"").decode("utf-8", errors="replace")[-2000:]
    if proc.returncode == 0:
        log.info("xrpl_refresh: ok duration_s=%.1f\n%s", duration, tail)
    else:
        log.error(
            "xrpl_refresh: FAILED rc=%d duration_s=%.1f\n%s",
            proc.returncode, duration, tail,
        )


def start_scheduler() -> None:
    """Start the APScheduler at FastAPI startup. Idempotent."""
    global _scheduler
    if _scheduler is not None:
        return

    sched = AsyncIOScheduler(timezone="UTC")
    sched.add_job(
        _run_intraday_crypto_refresh,
        trigger=CronTrigger(minute="*/15"),  # :00/:15/:30/:45 UTC
        id="intraday_crypto",
        name="Intraday crypto refresh + alerts",
        max_instances=1,      # never overlap a previous run
        coalesce=True,        # if we miss firings, collapse to one
        misfire_grace_time=600,
    )
    sched.add_job(
        _run_xrpl_refresh,
        # Every 6h starting at 02:07 UTC — offset from :00 so we don't
        # pile onto the intraday_crypto :00 firings, and from :15/:30/:45
        # so we never overlap. 6h cadence is well inside CoinGecko's
        # free-tier rate ceiling.
        trigger=CronTrigger(hour="*/6", minute="7"),
        id="xrpl_refresh",
        name="XRPL adoption metrics refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )
    sched.start()
    _scheduler = sched
    log.info("scheduler: started intraday_crypto (15min) + xrpl_refresh (6h)")


def stop_scheduler() -> None:
    """Stop the scheduler cleanly at FastAPI shutdown."""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    log.info("scheduler: stopped")
