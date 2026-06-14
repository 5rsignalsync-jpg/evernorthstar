"""Fernet-based encryption for Plaid access tokens at rest.

Plaid access tokens grant ongoing read access to the user's brokerage —
they MUST be encrypted at rest. We derive a Fernet key from settings.secret_key
so anyone who can read users.db cannot decrypt access tokens without also
having SECRET_KEY (which lives only in Fly secrets, not the volume).

Rotation: if SECRET_KEY changes, all existing tokens become undecryptable.
For now we accept that — users would need to re-link their accounts. A
future enhancement would store the key version per-row and support migration.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from crypto_trends.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-init the Fernet instance from SECRET_KEY.

    Fernet wants exactly 32 bytes of url-safe-b64-encoded key material. We
    derive it deterministically from SECRET_KEY so the key survives restarts.
    Fernet itself includes IV + HMAC so this is safe.
    """
    global _fernet
    if _fernet is not None:
        return _fernet
    if not settings.secret_key:
        raise RuntimeError(
            "Cannot encrypt portfolio tokens without SECRET_KEY. "
            "Set it in your environment / Fly secrets."
        )
    raw = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(raw)
    _fernet = Fernet(key)
    return _fernet


def encrypt_token(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError(
            "Failed to decrypt brokerage token. Did SECRET_KEY change? "
            "If yes, users will need to re-link their brokerage accounts."
        ) from e
