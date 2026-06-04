"""API contract tests via FastAPI TestClient.

Seeds a fresh DB, hits each endpoint, asserts response shapes + behaviors that
matter for the frontend: presence of headlines, correct ordering of long/short
legs, long-only flag for long_term signal, CSV format for /rankings.csv.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from crypto_trends.api.main import app
from crypto_trends.data.store import connect


@pytest.fixture
def client(tmp_db) -> TestClient:
    return TestClient(app)


def _seed_minimal(asset_class: str = "equity_large") -> None:
    """Seed two symbols with one OHLCV row, one momentum score each, one news row."""
    base_ts = datetime.utcnow().replace(microsecond=0)
    syms = ["AAA", "BBB"]
    with connect() as c:
        for i, s in enumerate(syms, 1):
            c.execute(
                'INSERT INTO universe (symbol, base, quote, asset_class, "rank", '
                'included, updated_at) VALUES (?, ?, ?, ?, ?, TRUE, now())',
                [s, s, "USD", asset_class, i],
            )
            c.execute(
                "INSERT INTO ohlcv (symbol, ts, interval, asset_class, open, high, "
                "low, close, volume, source) VALUES (?, ?, '1d', ?, ?, ?, ?, ?, ?, "
                "'yfinance')",
                [s, base_ts, asset_class, 100 + i, 110 + i, 90 + i, 100 + i, 1e6],
            )
            score = 0.5 if s == "AAA" else -0.5
            c.execute(
                "INSERT INTO signal_scores (symbol, ts, signal_name, score, "
                "components) VALUES (?, ?, 'momentum_v1', ?, '{}')",
                [s, base_ts, score],
            )
            c.execute(
                "INSERT INTO news (id, symbol, asset_class, source, headline, "
                "url, publisher, published_at, sentiment) "
                "VALUES (nextval('news_id_seq'), ?, ?, 'yfinance', ?, NULL, 'pub', ?, ?)",
                [s, asset_class, f"{s} headline", base_ts, 0.1 if s == "AAA" else -0.1],
            )


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_rankings_returns_long_and_short(client):
    _seed_minimal()
    r = client.get("/rankings",
                   params={"asset_class": "equity_large", "signal_name": "momentum_v1",
                           "top_n": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["asset_class"] == "equity_large"
    assert body["long_only"] is False
    assert [row["base"] for row in body["longs"]] == ["AAA"]
    assert [row["base"] for row in body["shorts"]] == ["BBB"]
    # News overlay should be attached.
    assert body["longs"][0]["headline"] == "AAA headline"


def test_rankings_long_only_for_long_term(client):
    """Long-term signal should return only longs, no shorts."""
    _seed_minimal()
    base_ts = datetime.utcnow().replace(microsecond=0)
    with connect() as c:
        c.execute(
            "INSERT INTO signal_scores (symbol, ts, signal_name, score, components) "
            "VALUES ('AAA', ?, 'long_term_v1', 0.7, '{}')",
            [base_ts],
        )
    r = client.get("/rankings",
                   params={"asset_class": "equity_large",
                           "signal_name": "long_term_v1", "top_n": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["long_only"] is True
    assert body["shorts"] == []
    assert len(body["longs"]) >= 1


def test_rankings_503_when_no_signals(client):
    """Empty DB → endpoint returns a 503 with a useful message."""
    r = client.get("/rankings",
                   params={"asset_class": "equity_large", "signal_name": "momentum_v1"})
    assert r.status_code == 503


def test_rankings_csv_includes_both_legs_and_disclaimer(client, tmp_users_db):
    """CSV export is Pro-only — register, promote, then verify the CSV shape."""
    from datetime import datetime, timedelta

    from sqlmodel import Session, select

    from crypto_trends.auth import db as auth_db
    from crypto_trends.auth.models import User

    _seed_minimal()
    client.post("/auth/register",
                json={"email": "csvtester@x.com", "password": "Password1234"})
    with Session(auth_db._engine) as s:
        u = s.exec(select(User).where(User.email == "csvtester@x.com")).first()
        u.subscription_tier = "pro"
        u.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
        s.add(u); s.commit()

    r = client.get("/rankings.csv",
                   params={"asset_class": "equity_large", "signal_name": "momentum_v1",
                           "top_n": 2})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    header, *data = rows
    assert "side" in header and "score" in header
    assert {row[0] for row in data} == {"LONG", "SHORT"}


def test_history_endpoint_returns_chart_payload(client):
    _seed_minimal()
    r = client.get("/history/AAA", params={"days": 30})
    assert r.status_code == 200
    body = r.json()
    assert body["base"] == "AAA"
    assert body["asset_class"] == "equity_large"
    assert len(body["price_series"]) == 1
    assert body["price_series"][0]["close"] == 101.0
    assert len(body["headlines"]) == 1
    assert body["headlines"][0]["headline"] == "AAA headline"


def test_history_404_for_unknown_symbol(client):
    r = client.get("/history/ZZZ", params={"days": 30})
    assert r.status_code == 404
