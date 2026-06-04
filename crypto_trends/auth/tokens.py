"""JWT encoding/decoding for session cookies.

We use a single short-lived JWT (7-day default) stored in an httpOnly+secure
cookie. There's no refresh-token rotation yet — that's a v2 concern. Logout
just clears the cookie. Sessions are stateless from the server's POV.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from crypto_trends.config import settings


def encode_session(user_id: int) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.jwt_expiration_days)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_session(token: str) -> int | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (jwt.PyJWTError, ValueError):
        return None
