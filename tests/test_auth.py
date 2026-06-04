"""Auth + session smoke tests.

Covers /auth/register, /auth/login, /auth/logout, /auth/me — plus the
password-hashing and JWT round-trip primitives. Each test gets a fresh
SQLite via the `tmp_users_db` fixture.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from crypto_trends.api.main import app
from crypto_trends.auth.passwords import hash_password, verify_password
from crypto_trends.auth.tokens import decode_session, encode_session


# ---------- primitives ---------------------------------------------------

def test_password_hash_roundtrip():
    h = hash_password("Hunter2hunter2")
    assert h != "Hunter2hunter2"           # never store plaintext
    assert h.startswith("$2b$")            # bcrypt prefix
    assert verify_password("Hunter2hunter2", h) is True
    assert verify_password("wrong-pw", h) is False


def test_password_hash_handles_long_input():
    # SHA-256 pre-hash should sidestep bcrypt's 72-byte limit.
    long_pw = "x" * 500
    h = hash_password(long_pw)
    assert verify_password(long_pw, h) is True


def test_jwt_roundtrip():
    tok = encode_session(42)
    assert decode_session(tok) == 42
    # Tampered token returns None, never raises
    assert decode_session(tok[:-2] + "XX") is None
    assert decode_session("garbage") is None
    assert decode_session("") is None


# ---------- HTTP flow ----------------------------------------------------

@pytest.fixture
def client(tmp_users_db) -> TestClient:
    return TestClient(app)


def test_register_creates_user_and_sets_cookie(client):
    r = client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "Password1234"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["subscription_tier"] == "free"
    assert body["is_pro"] is False
    # Cookie set
    assert "crypto_trends_session" in {c.name for c in r.cookies.jar}


def test_register_rejects_short_password(client):
    r = client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "short"},
    )
    assert r.status_code == 400
    assert "at least 8 characters" in r.json()["detail"].lower()


def test_register_rejects_duplicate_email(client):
    client.post("/auth/register",
                json={"email": "a@b.com", "password": "Password1234"})
    r = client.post("/auth/register",
                    json={"email": "a@b.com", "password": "Password9999"})
    assert r.status_code == 409


def test_register_normalizes_email_case(client):
    client.post("/auth/register",
                json={"email": "Mixed@Example.com", "password": "Password1234"})
    # Duplicate with different casing should be rejected
    r = client.post("/auth/register",
                    json={"email": "mixed@example.com", "password": "Other1234"})
    assert r.status_code == 409


def test_login_with_correct_credentials(client):
    client.post("/auth/register",
                json={"email": "bob@example.com", "password": "Password1234"})
    # Fresh client to drop cookies
    fresh = TestClient(app)
    r = fresh.post("/auth/login",
                   json={"email": "bob@example.com", "password": "Password1234"})
    assert r.status_code == 200
    assert r.json()["email"] == "bob@example.com"


def test_login_rejects_wrong_password(client):
    client.post("/auth/register",
                json={"email": "bob@example.com", "password": "Password1234"})
    fresh = TestClient(app)
    r = fresh.post("/auth/login",
                   json={"email": "bob@example.com", "password": "WrongOne1234"})
    assert r.status_code == 401
    # Message doesn't reveal whether email exists (anti-enumeration)
    assert "invalid" in r.json()["detail"].lower()


def test_login_rejects_unknown_email_same_error_as_wrong_password(client):
    fresh = TestClient(app)
    r = fresh.post("/auth/login",
                   json={"email": "nobody@example.com", "password": "Password1234"})
    assert r.status_code == 401


def test_me_returns_user_when_logged_in(client):
    client.post("/auth/register",
                json={"email": "carol@example.com", "password": "Password1234"})
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "carol@example.com"


def test_me_returns_null_when_logged_out(tmp_users_db):
    fresh = TestClient(app)
    r = fresh.get("/auth/me")
    # Either 200 with body=null, or returns None — endpoint allows anon
    assert r.status_code == 200
    assert r.json() is None


def test_logout_clears_cookie(client):
    client.post("/auth/register",
                json={"email": "d@b.com", "password": "Password1234"})
    assert client.get("/auth/me").json()["email"] == "d@b.com"
    r = client.post("/auth/logout")
    assert r.status_code == 200
    # After logout /me returns null
    assert client.get("/auth/me").json() is None
