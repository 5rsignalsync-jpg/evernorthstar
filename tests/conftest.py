"""Shared pytest fixtures.

`tmp_db`        — fresh DuckDB (analytics).
`tmp_users_db`  — fresh SQLite (auth/users/payments).
`client`        — FastAPI TestClient with both DBs isolated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crypto_trends.config import settings
from crypto_trends.data.store import init_db


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch):
    """Yields a path to a fresh DuckDB with the schema applied."""
    db_path = tmp_path / "test.duckdb"
    monkeypatch.setattr(settings, "duckdb_path", db_path)
    init_db()
    yield db_path


@pytest.fixture
def tmp_users_db(tmp_path: Path, monkeypatch):
    """Yields a path to a fresh SQLite user/auth DB, rebound globally for the test.

    Rebinds both `settings.users_db_path` AND the cached `_engine` in auth.db
    so any code that imported the engine before the test runs sees the new DB.
    """
    db_path = tmp_path / "test-users.db"
    monkeypatch.setattr(settings, "users_db_path", db_path)

    from sqlmodel import create_engine

    from crypto_trends.auth import db as auth_db

    new_engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(auth_db, "_engine", new_engine)
    auth_db.init_users_db()
    yield db_path
