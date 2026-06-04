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
    """Idempotent — creates the schema if missing."""
    SQLModel.metadata.create_all(_engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session, closes it after the request."""
    with Session(_engine) as session:
        yield session
