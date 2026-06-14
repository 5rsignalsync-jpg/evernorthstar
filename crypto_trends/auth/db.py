"""SQLite engine + session factory for the user store.

Deliberately separate from the DuckDB analytics file — DuckDB is great at
columnar analytics, terrible at concurrent OLTP writes. SQLite handles the
auth/users/payments domain with zero infra cost and is fine up to thousands
of users on a single Fly volume.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from crypto_trends.auth import models  # noqa: F401 — register model metadata
from crypto_trends.portfolio import models as portfolio_models  # noqa: F401 — same
from crypto_trends.config import settings


def _engine_url() -> str:
    settings.users_db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{settings.users_db_path}"


_engine = create_engine(
    _engine_url(),
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_users_db() -> None:
    """Idempotent — creates the schema if missing, runs additive migrations.

    SQLModel.metadata.create_all only creates *missing* tables; it does NOT
    add columns to existing tables. For lightweight schema evolution we run
    additive ALTER TABLE ADD COLUMN here, swallowing the OperationalError
    when the column already exists. SQLite has no IF NOT EXISTS on ADD COLUMN,
    so try/except is the idiomatic pattern.
    """
    SQLModel.metadata.create_all(_engine)
    _run_lightweight_migrations()


def _run_lightweight_migrations() -> None:
    from sqlalchemy import text
    additions = [
        # column, type, default — keep this list strictly additive
        ("daily_digest_opt_in", "INTEGER NOT NULL DEFAULT 0"),
        ("daily_digest_last_sent_at", "DATETIME"),
    ]
    with _engine.begin() as conn:
        for col, ddl in additions:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
            except Exception:
                # already exists — fine
                pass


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session, closes it after the request."""
    with Session(_engine) as session:
        yield session
