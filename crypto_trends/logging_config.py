"""Centralized logging setup.

Call `configure()` from CLI entry points and long-running processes.
Library modules should just `logger = logging.getLogger(__name__)` and use it —
they should not configure formatting themselves.
"""

from __future__ import annotations

import logging
import os
import sys


def configure(level: str | int = "INFO") -> None:
    """Configure root logger with a sensible production-shaped format.

    Set LOG_LEVEL=DEBUG (or WARNING etc.) in env to override.
    """
    if isinstance(level, str):
        level = level.upper()

    env_level = os.environ.get("LOG_LEVEL")
    final = env_level.upper() if env_level else level

    root = logging.getLogger()
    # Avoid double-configuring under uvicorn reload or multiple CLI invocations
    if any(getattr(h, "_crypto_trends", False) for h in root.handlers):
        root.setLevel(final)
        return

    handler = logging.StreamHandler(stream=sys.stderr)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    handler._crypto_trends = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(final)

    # Quiet noisy third-party loggers.
    for noisy in ("urllib3", "httpx", "httpcore", "yfinance", "peewee"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
