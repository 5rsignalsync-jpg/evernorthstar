"""Initialize the DuckDB schema. Idempotent."""

from crypto_trends.data.store import init_db
from crypto_trends.config import settings


if __name__ == "__main__":
    init_db()
    print(f"Schema applied at {settings.duckdb_path}")
