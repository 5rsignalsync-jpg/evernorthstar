# 5R Signal Sync — FastAPI backend image for Fly.io.
#
# Architecture:
#   - python:3.12-slim base (~50MB before deps)
#   - uv handles deps via uv.lock for reproducible builds
#   - Single uvicorn worker (SQLite users.db requires it)
#   - DuckDB analytics + SQLite auth live on /data (Fly persistent volume)
#   - Listens on $PORT (Fly injects 8080 by default)
#
# Slimming notes:
#   torch + transformers (FinBERT) are in pyproject for the local refresh
#   pipeline. They add ~500MB to the image but are never imported at request
#   time (lazy-loaded only by the rescore CLI). Worth keeping in so the same
#   container can also run scripts/refresh_all.py via `fly ssh console` if you
#   later move refresh off GitHub Actions.

FROM python:3.12-slim AS builder

# Build deps: curl for uv installer, build-essential for any C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy lockfile + project metadata first so deps can be cached across code changes.
# README.md is not present in this repo; pyproject doesn't reference it either.
COPY pyproject.toml uv.lock ./
COPY crypto_trends/__init__.py crypto_trends/__init__.py

# Install deps into a project-local .venv. --no-dev skips pytest/ruff.
# --frozen ensures uv.lock is honored (fails build if lock is out of date).
RUN uv sync --frozen --no-dev

# Now copy the rest of the source (separate layer = faster rebuilds on code-only changes)
COPY crypto_trends ./crypto_trends
COPY scripts ./scripts


# --- runtime stage --------------------------------------------------------
FROM python:3.12-slim AS runtime

# Runtime deps: ca-certs for HTTPS (Stripe, FMP, Binance), libgomp for numpy/scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the built virtualenv + source from builder
COPY --from=builder /app /app

# Put the venv on PATH so `python` and installed scripts resolve correctly
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Fly persistent volume gets mounted here (fly.toml [mounts]). DuckDB +
# SQLite both live on it, so data survives machine restarts.
RUN mkdir -p /data
ENV DUCKDB_PATH=/data/crypto_trends.duckdb \
    USERS_DB_PATH=/data/users.db

EXPOSE 8080

# Single worker is REQUIRED — SQLite users.db will corrupt with concurrent writers.
# startup_checks.py asserts UVICORN_WORKERS=1 in prod.
CMD ["uvicorn", "crypto_trends.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
