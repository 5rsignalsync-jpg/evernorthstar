from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import duckdb

from crypto_trends.config import settings

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect(read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    _ensure_parent(settings.duckdb_path)
    conn = duckdb.connect(str(settings.duckdb_path), read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Apply schema. Idempotent."""
    schema_sql = SCHEMA_PATH.read_text()
    with connect() as conn:
        conn.execute(schema_sql)


if __name__ == "__main__":
    init_db()
    print(f"Schema applied at {settings.duckdb_path}")
