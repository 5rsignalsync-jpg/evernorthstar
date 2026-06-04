"""Tier gating tests: free vs pro on /rankings, /rankings.csv, and the
tier limits exported to the frontend.

Pre-seeds a small set of OHLCV + signal rows so /rankings returns
something the client can be clamped against.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from crypto_trends.api.main import app
from crypto_trends.auth import db as auth_db
from crypto_trends.auth.models import User
from crypto_trends.auth.tiers import FREE, PRO, limits_for
from crypto_trends.data.store import connect


# ---------- pure-function tier limits ------------------------------------

def test_free_limits_are_restrictive():
    assert FREE.tier_name == "free"
    assert FREE.top_n == 3
    assert FREE.csv_export is False
    assert FREE.realtime_refresh is False
    assert FREE.watchlist_max == 5


def test_pro_limits_are_open():
    assert PRO.tier_name == "pro"
    assert PRO.top_n == 25
    assert PRO.csv_export is True
    assert PRO.realtime_refresh is True
    assert PRO.watchlist_max >= 10_000


def test_anon_gets_free_limits():
    assert limits_for(None) is FREE


def test_unsubscribed_user_gets_free_limits(tmp_users_db):
    user = User(email="free@x.com", password_hash="x", subscription_tier="free")
    assert limits_for(user) is FREE


def test_pro_user_with_valid_expiry_gets_pro_limits(tmp_users_db):
    user = User(
        email="pro@x.com", password_hash="x", subscription_tier="pro",
        subscription_expires_at=datetime.utcnow() + timedelta(days=30),
    )
    assert limits_for(user) is PRO


def test_pro_user_with_expired_subscription_falls_back_to_free(tmp_users_db):
    user = User(
        email="exp@x.com", password_hash="x", subscription_tier="pro",
        subscription_expires_at=datetime.utcnow() - timedelta(days=1),
    )
    assert limits_for(user) is FREE


def test_founder_lifetime_with_null_expiry_gets_pro_limits(tmp_users_db):
    user = User(
        email="founder@x.com", password_hash="x",
        subscription_tier="founder_lifetime", subscription_expires_at=None,
    )
    assert limits_for(user) is PRO


# ---------- /rankings tier clamping --------------------------------------

def _seed_signals(asset_class: str = "equity_large", n: int = 10) -> None:
    """Seed `n` symbols with one OHLCV row, one momentum score each."""
    base_ts = datetime.utcnow().replace(microsecond=0)
    with connect() as c:
        for i in range(n):
            sym = f"TEST{i:02d}"
            c.execute(
                'INSERT INTO universe (symbol, base, quote, asset_class, "rank", '
                'included, updated_at) VALUES (?, ?, ?, ?, ?, TRUE, now())',
                [sym, sym, "USD", asset_class, i + 1],
            )
            c.execute(
                "INSERT INTO ohlcv (symbol, ts, interval, asset_class, open, high, "
                "low, close, volume, source) VALUES (?, ?, '1d', ?, 100, 110, 90, "
                "100, 1e6, 'test')",
                [sym, base_ts, asset_class],
            )
            # Spread scores from +0.9 down to -0.9 so we have clear longs/shorts.
            score = 0.9 - (i * 1.8 / max(n - 1, 1))
            c.execute(
                "INSERT INTO signal_scores (symbol, ts, signal_name, score, "
                "components) VALUES (?, ?, 'momentum_v1', ?, '{}')",
                [sym, base_ts, score],
            )


@pytest.fixture
def seeded_client(tmp_db, tmp_users_db) -> TestClient:
    _seed_signals(n=10)
    return TestClient(app)


def _promote_to_pro(email: str) -> None:
    with Session(auth_db._engine) as s:
        user = s.exec(select(User).where(User.email == email)).first()
        assert user is not None, f"user {email} not found"
        user.subscription_tier = "pro"
        user.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
        s.add(user)
        s.commit()


def test_anon_rankings_clamped_to_free_top_n(seeded_client):
    r = seeded_client.get(
        "/rankings",
        params={"asset_class": "equity_large", "signal_name": "momentum_v1",
                "top_n": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "free"
    assert body["requested_top_n"] == 10
    assert body["delivered_top_n"] == FREE.top_n
    assert len(body["longs"]) == FREE.top_n
    assert len(body["shorts"]) == FREE.top_n
    assert "Upgrade" in (body["upsell_text"] or "")


def test_pro_rankings_get_full_top_n(seeded_client):
    seeded_client.post(
        "/auth/register",
        json={"email": "prouser@x.com", "password": "Password1234"},
    )
    _promote_to_pro("prouser@x.com")
    # Trigger a fresh me-fetch so the cookie still maps to a real user
    r = seeded_client.get(
        "/rankings",
        params={"asset_class": "equity_large", "signal_name": "momentum_v1",
                "top_n": 10},
    )
    body = r.json()
    assert body["tier"] == "pro"
    assert body["delivered_top_n"] == 10
    assert body["upsell_text"] is None
    assert len(body["longs"]) == 10
    assert len(body["shorts"]) == 10


def test_csv_export_requires_pro(seeded_client):
    # Anonymous → 401 (require_user)
    r = seeded_client.get(
        "/rankings.csv",
        params={"asset_class": "equity_large", "signal_name": "momentum_v1"},
    )
    assert r.status_code == 401

    # Free-tier registered user → 402 (require_pro)
    seeded_client.post(
        "/auth/register",
        json={"email": "freeuser@x.com", "password": "Password1234"},
    )
    r = seeded_client.get(
        "/rankings.csv",
        params={"asset_class": "equity_large", "signal_name": "momentum_v1"},
    )
    assert r.status_code == 402


def test_csv_export_works_for_pro(seeded_client):
    seeded_client.post(
        "/auth/register",
        json={"email": "csvuser@x.com", "password": "Password1234"},
    )
    _promote_to_pro("csvuser@x.com")
    r = seeded_client.get(
        "/rankings.csv",
        params={"asset_class": "equity_large", "signal_name": "momentum_v1"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert b"side,rank,symbol" in r.content
