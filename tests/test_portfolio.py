"""Tests for portfolio routes + analysis + encryption.

Covers: encryption round-trip, Pro gating on /portfolio endpoints,
disconnect cross-user isolation, analysis with no holdings, analysis with
holdings that have signal scores + smart-money disclosures.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from crypto_trends.api.main import app
from crypto_trends.auth import db as auth_db
from crypto_trends.auth.models import User
from crypto_trends.data.store import connect
from crypto_trends.portfolio import analysis
from crypto_trends.portfolio.encryption import decrypt_token, encrypt_token
from crypto_trends.portfolio.models import BrokerageAccount, Holding


def test_encryption_round_trip(tmp_users_db):
    tok = "access-sandbox-fake-abc123xyz"
    ct = encrypt_token(tok)
    assert ct != tok
    assert decrypt_token(ct) == tok


def test_encryption_different_each_time(tmp_users_db):
    """Fernet includes a random IV so ciphertexts differ per call."""
    tok = "same-input"
    assert encrypt_token(tok) != encrypt_token(tok)


def test_portfolio_endpoint_requires_pro(tmp_db, tmp_users_db):
    client = TestClient(app)
    client.post("/auth/register", json={"email": "free@example.com", "password": "Password!1"})
    r = client.get("/portfolio")
    # Free user hits require_pro dependency
    assert r.status_code in (401, 402, 403), r.text


def test_link_token_returns_503_when_plaid_not_configured(tmp_db, tmp_users_db):
    client = TestClient(app)
    client.post("/auth/register", json={"email": "pro@example.com", "password": "Password!1"})
    # Promote to pro
    with Session(auth_db._engine) as s:
        u = s.exec(select(User).where(User.email == "pro@example.com")).first()
        u.subscription_tier = "pro"
        u.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
        s.add(u); s.commit()
    r = client.post("/portfolio/link-token")
    # Plaid sandbox creds not set in tests, should 503 with friendly message
    assert r.status_code == 503
    assert "coming soon" in r.json()["detail"].lower()


def test_portfolio_endpoint_empty_for_no_accounts(tmp_db, tmp_users_db):
    client = TestClient(app)
    client.post("/auth/register", json={"email": "pro@example.com", "password": "Password!1"})
    with Session(auth_db._engine) as s:
        u = s.exec(select(User).where(User.email == "pro@example.com")).first()
        u.subscription_tier = "pro"
        u.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
        s.add(u); s.commit()
    r = client.get("/portfolio")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["n_holdings"] == 0
    assert body["accounts"] == []
    assert body["holdings"] == []


def test_disconnect_cross_user_isolation(tmp_db, tmp_users_db):
    """User B cannot disconnect User A's brokerage account."""
    client = TestClient(app)
    # User A signs up, gets pro, has an account
    client.post("/auth/register", json={"email": "alice@example.com", "password": "Password!1"})
    with Session(auth_db._engine) as s:
        u = s.exec(select(User).where(User.email == "alice@example.com")).first()
        u.subscription_tier = "pro"
        u.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
        s.add(u); s.commit()
        s.refresh(u)
        account = BrokerageAccount(
            user_id=u.id, plaid_item_id="alice_item_1",
            access_token_encrypted=encrypt_token("access-fake"),
            institution_name="Test Bank",
        )
        s.add(account); s.commit(); s.refresh(account)
        alice_account_id = account.id

    client.post("/auth/logout")
    # User B signs up, gets pro
    client.post("/auth/register", json={"email": "bob@example.com", "password": "Password!1"})
    with Session(auth_db._engine) as s:
        u = s.exec(select(User).where(User.email == "bob@example.com")).first()
        u.subscription_tier = "pro"
        u.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
        s.add(u); s.commit()

    r = client.delete(f"/portfolio/accounts/{alice_account_id}")
    assert r.status_code == 404


def _seed_user_and_account(email: str) -> tuple[int, int]:
    """Helper: register user, mark pro, attach one brokerage account."""
    with Session(auth_db._engine) as s:
        u = User(email=email, password_hash="x",
                 subscription_tier="pro",
                 subscription_expires_at=datetime.utcnow() + timedelta(days=30))
        s.add(u); s.commit(); s.refresh(u)
        a = BrokerageAccount(
            user_id=u.id, plaid_item_id=f"{email}_item",
            access_token_encrypted=encrypt_token("access-fake"),
            institution_name="Test Bank",
        )
        s.add(a); s.commit(); s.refresh(a)
        return u.id, a.id


def test_analysis_with_no_signal_data(tmp_db, tmp_users_db):
    user_id, account_id = _seed_user_and_account("eve@example.com")
    with Session(auth_db._engine) as s:
        s.add(Holding(account_id=account_id, user_id=user_id,
                      ticker="ZZZNOSCORE", name="Unknown Corp",
                      quantity=10, price=5.0, value=50.0))
        s.commit()
    summary, holdings = analysis.analyze_user_portfolio(user_id)
    assert summary.n_holdings == 1
    assert summary.total_value_usd == 50.0
    assert summary.n_with_signal == 0
    assert summary.weighted_momentum_score is None
    assert summary.momentum_quality_label == "unscored"
    assert holdings[0].momentum_score is None


def test_analysis_annotates_with_signal_score(tmp_db, tmp_users_db):
    user_id, account_id = _seed_user_and_account("fran@example.com")
    # Seed a signal_score for AAPL
    ts = datetime.utcnow().replace(microsecond=0)
    with connect() as c:
        c.execute(
            'INSERT INTO universe (symbol, base, quote, asset_class, "rank", '
            'included, updated_at) VALUES (?, ?, ?, ?, 1, TRUE, now())',
            ["AAPL", "AAPL", "USD", "equity_large"],
        )
        c.execute(
            "INSERT INTO signal_scores (symbol, ts, signal_name, score, components) "
            "VALUES (?, ?, 'momentum_v1', ?, '{}')",
            ["AAPL", ts, 0.65],
        )
    # Add the holding
    with Session(auth_db._engine) as s:
        s.add(Holding(account_id=account_id, user_id=user_id,
                      ticker="AAPL", name="Apple Inc",
                      quantity=10, price=150.0, value=1500.0))
        s.commit()
    summary, holdings = analysis.analyze_user_portfolio(user_id)
    assert summary.n_with_signal == 1
    assert summary.weighted_momentum_score == pytest.approx(0.65)
    assert summary.momentum_quality_label == "strong"
    assert holdings[0].momentum_score == pytest.approx(0.65)
    assert holdings[0].asset_class == "equity_large"


def test_analysis_annotates_with_smart_money(tmp_db, tmp_users_db):
    user_id, account_id = _seed_user_and_account("gus@example.com")
    # Seed a smart_money trade. id is BIGINT NOT NULL without an auto-increment
    # in DuckDB so we set it explicitly. In production, the ingest pipeline
    # uses ROW_NUMBER()-based id assignment.
    with connect() as c:
        c.execute(
            "INSERT INTO smart_money_trades (id, source, actor_id, actor_name, ticker, "
            "side, disclosure_date, amount_min) VALUES "
            "(1, '13F', 'BRK', 'Berkshire Hathaway', 'AAPL', 'buy', ?, 1000000)",
            [date.today() - timedelta(days=30)],
        )
    with Session(auth_db._engine) as s:
        s.add(Holding(account_id=account_id, user_id=user_id,
                      ticker="AAPL", name="Apple Inc",
                      quantity=10, price=150.0, value=1500.0))
        s.commit()
    summary, holdings = analysis.analyze_user_portfolio(user_id)
    assert summary.n_with_smart_money == 1
    assert summary.smart_money_overlap_pct == pytest.approx(100.0)
    assert "Berkshire Hathaway" in holdings[0].smart_money_actors
    assert holdings[0].smart_money_buys_usd == pytest.approx(1000000)


def test_analysis_weighted_score_respects_position_size(tmp_db, tmp_users_db):
    """A small +0.9 position shouldn't outweigh a large -0.5 position."""
    user_id, account_id = _seed_user_and_account("hugo@example.com")
    ts = datetime.utcnow().replace(microsecond=0)
    with connect() as c:
        for sym, score in [("BIGNEG", -0.5), ("SMALLPOS", 0.9)]:
            c.execute(
                'INSERT INTO universe (symbol, base, quote, asset_class, "rank", '
                'included, updated_at) VALUES (?, ?, ?, ?, 1, TRUE, now())',
                [sym, sym, "USD", "equity_large"],
            )
            c.execute(
                "INSERT INTO signal_scores (symbol, ts, signal_name, score, components) "
                "VALUES (?, ?, 'momentum_v1', ?, '{}')",
                [sym, ts, score],
            )
    with Session(auth_db._engine) as s:
        s.add(Holding(account_id=account_id, user_id=user_id,
                      ticker="BIGNEG", name="Big Negative",
                      quantity=10, value=10000))
        s.add(Holding(account_id=account_id, user_id=user_id,
                      ticker="SMALLPOS", name="Small Positive",
                      quantity=1, value=100))
        s.commit()
    summary, _ = analysis.analyze_user_portfolio(user_id)
    # Expected: (-0.5 * 10000 + 0.9 * 100) / 10100 ≈ -0.486
    assert summary.weighted_momentum_score == pytest.approx(-0.486, abs=0.01)
    assert summary.momentum_quality_label == "weak"
