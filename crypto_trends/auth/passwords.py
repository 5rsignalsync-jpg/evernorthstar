"""bcrypt password hashing (direct, no passlib).

passlib 1.7.4 has known incompatibilities with bcrypt ≥5.x; using bcrypt
directly is one less moving part. bcrypt enforces a 72-byte password ceiling,
so we hash the input via SHA-256 first — that gives unlimited input length
without weakening the bcrypt cost factor.
"""

from __future__ import annotations

import base64
import hashlib

import bcrypt

_ROUNDS = 12  # default work factor; ~0.3s/hash on a 2024 laptop


def _prehash(password: str) -> bytes:
    # SHA-256 of the password, base64-encoded — produces a 44-byte ASCII string
    # that's well under bcrypt's 72-byte limit and won't trigger truncation.
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=_ROUNDS)
    return bcrypt.hashpw(_prehash(password), salt).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False
