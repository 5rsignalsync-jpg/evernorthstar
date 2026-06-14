"""Tests for the alert rules CRUD + runner.

Covers: free-tier cap (3 rules), cross-user isolation, rule evaluation,
cooldown enforcement, and the AlertEvent history trail.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from crypto_trends.alerts import runner
from crypto_trends.api.main import app
from crypto_trends.auth import db as auth_db
from crypto_trends.auth.models import AlertEvent, AlertRule, User
from crypto_trends.data.store import connect


def _seed_one_score(symbol: str, score: float) -> None:
    """One universe row + one ohlcv row + one signal score for `symbol`."""
    ts = datetime.utcnow().replace(microsecond=0)
    with connect() as c:
        c.execute(
            'INSERT INTO universe (symbol, base, quote, asset_class, "rank", '
            'included, updated_at) VALUES (?, ?, ?, ?, 1, TRUE, now())',
            [symbol, symbol, "USD", "equity_large"],
        )
        c.execute(
            "INSERT INTO ohlcv (symbol, ts, interval, asset_class, open, high, "
            "low, close, volume, source) VALUES (?, ?, '1d', ?, 100, 110, 90, "
            "?, 1e6, 'test')",
            [symbol, ts, "equity_large", 100.0],
        )
        c.execute(
            "INSERT INTO signal_scores (symbol, ts, signal_name, score, "
            "components) VALUES (?, ?, 'momentum_v1', ?, '{}')",
            [symbol, ts, score],
        )


def _register_and_login(client: TestClient, email: str, pw: str = "Password!1") -> dict:
    r = client.post("/auth/register", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()


def test_create_alert_rule_persists(tmp_db, tmp_users_db):
    client = TestClient(app)
    _register_and_login(client, "alice@example.com")
    r = client.post("/alerts", json={
        "symbol": "AAPL",
        "asset_class": "equity_large",
        "condition": "score_above",
        "threshold": 0.5,
    })
    assert r.status_code == 201, r.text
    rule = r.json()
    assert rule["symbol"] == "AAPL"
    assert rule["enabled"] is True


def test_free_tier_capped_at_three_rules(tmp_db, tmp_users_db):
    client = TestClient(app)
    _register_and_login(client, "bob@example.com")
    for i in range(3):
        r = client.post("/alerts", json={
            "symbol": f"TEST{i}",
            "asset_class": "equity_large",
            "condition": "score_above",
            "threshold": 0.5,
        })
        assert r.status_code == 201
    # 4th should be rejected
    r = client.post("/alerts", json={
        "symbol": "TEST4",
        "asset_class": "equity_large",
        "condition": "score_above",
        "threshold": 0.5,
    })
    assert r.status_code == 402
    assert "Free tier" in r.json()["detail"]


def test_invalid_condition_rejected(tmp_db, tmp_users_db):
    client = TestClient(app)
    _register_and_login(client, "carol@example.com")
    r = client.post("/alerts", json={
        "symbol": "AAPL",
        "asset_class": "equity_large",
        "condition": "score_eq",   # not allowed
        "threshold": 0.5,
    })
    assert r.status_code == 422


def test_cross_user_rule_isolation(tmp_db, tmp_users_db):
    client = TestClient(app)
    _register_and_login(client, "alice@example.com")
    r = client.post("/alerts", json={
        "symbol": "AAPL", "asset_class": "equity_large",
        "condition": "score_above", "threshold": 0.5,
    })
    alice_rule_id = r.json()["id"]
    client.post("/auth/logout")

    _register_and_login(client, "mallory@example.com")
    # Mallory should not be able to delete Alice's rule.
    r = client.delete(f"/alerts/{alice_rule_id}")
    assert r.status_code == 404
    # Nor see it in her list.
    r = client.get("/alerts")
    assert r.json() == []


def test_runner_fires_on_score_above(tmp_db, tmp_users_db):
    _seed_one_score("AAPL", 0.8)
    with Session(auth_db._engine) as s:
        user = User(email="dave@example.com", password_hash="x")
        s.add(user); s.commit(); s.refresh(user)
        rule = AlertRule(
            user_id=user.id, symbol="AAPL", asset_class="equity_large",
            condition="score_above", threshold=0.5, enabled=True,
        )
        s.add(rule); s.commit(); s.refresh(rule)
        rule_id = rule.id

    result = runner.run_alerts()
    assert result["scanned"] == 1
    assert result["triggered"] == 1
    # emails_sent=0 because RESEND_API_KEY isn't set in tests, but the AlertEvent
    # is still recorded for history visibility.
    with Session(auth_db._engine) as s:
        events = s.exec(select(AlertEvent).where(AlertEvent.rule_id == rule_id)).all()
        assert len(events) == 1
        assert events[0].observed_value == pytest.approx(0.8)
        assert events[0].email_sent is False  # no Resend key in tests


def test_runner_does_not_fire_when_below_threshold(tmp_db, tmp_users_db):
    _seed_one_score("AAPL", 0.2)  # below threshold
    with Session(auth_db._engine) as s:
        user = User(email="eve@example.com", password_hash="x")
        s.add(user); s.commit(); s.refresh(user)
        rule = AlertRule(
            user_id=user.id, symbol="AAPL", asset_class="equity_large",
            condition="score_above", threshold=0.5, enabled=True,
        )
        s.add(rule); s.commit()
    result = runner.run_alerts()
    assert result["triggered"] == 0


def test_runner_respects_cooldown(tmp_db, tmp_users_db):
    _seed_one_score("AAPL", 0.8)
    with Session(auth_db._engine) as s:
        user = User(email="frank@example.com", password_hash="x")
        s.add(user); s.commit(); s.refresh(user)
        rule = AlertRule(
            user_id=user.id, symbol="AAPL", asset_class="equity_large",
            condition="score_above", threshold=0.5, enabled=True,
            # Triggered 1h ago — within the 6h cooldown
            last_triggered_at=datetime.utcnow() - timedelta(hours=1),
        )
        s.add(rule); s.commit()
    result = runner.run_alerts()
    assert result["triggered"] == 0
    assert result["cooled_down"] == 1


def test_runner_re_fires_after_cooldown(tmp_db, tmp_users_db):
    _seed_one_score("AAPL", 0.8)
    with Session(auth_db._engine) as s:
        user = User(email="grace@example.com", password_hash="x")
        s.add(user); s.commit(); s.refresh(user)
        rule = AlertRule(
            user_id=user.id, symbol="AAPL", asset_class="equity_large",
            condition="score_above", threshold=0.5, enabled=True,
            # Triggered 10h ago — past the 6h cooldown
            last_triggered_at=datetime.utcnow() - timedelta(hours=10),
        )
        s.add(rule); s.commit()
    result = runner.run_alerts()
    assert result["triggered"] == 1


def test_disabled_rule_does_not_fire(tmp_db, tmp_users_db):
    _seed_one_score("AAPL", 0.9)
    with Session(auth_db._engine) as s:
        user = User(email="hank@example.com", password_hash="x")
        s.add(user); s.commit(); s.refresh(user)
        rule = AlertRule(
            user_id=user.id, symbol="AAPL", asset_class="equity_large",
            condition="score_above", threshold=0.5, enabled=False,  # OFF
        )
        s.add(rule); s.commit()
    result = runner.run_alerts()
    assert result["scanned"] == 0  # disabled rules not even scanned


def test_price_condition_fires_on_close(tmp_db, tmp_users_db):
    _seed_one_score("AAPL", 0.0)  # seed sets close = 100
    with Session(auth_db._engine) as s:
        user = User(email="ivy@example.com", password_hash="x")
        s.add(user); s.commit(); s.refresh(user)
        rule = AlertRule(
            user_id=user.id, symbol="AAPL", asset_class="equity_large",
            condition="price_above", threshold=50.0, enabled=True,
        )
        s.add(rule); s.commit()
    result = runner.run_alerts()
    assert result["triggered"] == 1
