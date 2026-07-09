"""CCXT-based crypto exchange sync.

Read-only fetch of balances from a user-supplied API key + secret via CCXT's
unified interface. Zero per-exchange code — supporting a new exchange is a
one-line whitelist entry.

Security posture:
  - Keys are Fernet-encrypted at rest with the same secret used for Plaid.
  - We ONLY call fetch_balance() — never trade / transfer / withdraw.
  - Raw keys are never logged; error messages are sanitized to strip any
    accidental substring match against the plaintext key.
  - Read-only key expectation is communicated in the UI, but we can't
    verify the key's actual permission scope through CCXT (each exchange
    handles permissions differently). Users who paste trading-enabled keys
    are on their own — but our code never issues a trading call.

Cost basis:
  - fetch_balance() returns quantities only; no historical cost.
  - On first sync, we set cost_basis_per_share = current_price (breakeven)
    so unrealized PL is $0. User can override via Edit later. This matches
    Merlin's behavior for wallet imports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import ccxt

from crypto_trends.portfolio.encryption import decrypt_token

log = logging.getLogger(__name__)

# Whitelist of supported exchange ids (must match ccxt's exchange registry).
# When adding: verify CCXT supports fetch_balance() for it, and confirm the
# auth model (some need a passphrase in addition to key + secret).
#
# `requires_passphrase` matches which exchanges historically need a third
# credential — coinbase (Coinbase Advanced), kucoin, okx. binanceus and
# kraken and gemini are key+secret only. If we later add an exchange whose
# scheme changes, update this map + the frontend picker's `needs_passphrase`
# entry in tandem.
SUPPORTED_EXCHANGES: dict[str, dict] = {
    "coinbase": {
        "label": "Coinbase",
        "requires_passphrase": True,   # Coinbase Advanced Trade uses passphrase
        "note": "Use an Advanced Trade API key with the 'view' permission only.",
    },
    "binanceus": {
        "label": "Binance.US",
        "requires_passphrase": False,
        "note": "Under Binance.US → API Management. Restrict to 'Read Info' only.",
    },
    "kraken": {
        "label": "Kraken",
        "requires_passphrase": False,
        "note": "Under Settings → API. Enable only 'Query Funds' + 'Query Open Orders'.",
    },
    "gemini": {
        "label": "Gemini",
        "requires_passphrase": False,
        "note": "Under Account → API. Choose 'Auditor' scope (read-only).",
    },
    "kucoin": {
        "label": "KuCoin",
        "requires_passphrase": True,
        "note": "Under API Management. General permission only — no Trade.",
    },
    "bybit": {
        "label": "Bybit",
        "requires_passphrase": False,
        "note": "Read-only permission is a checkbox at key creation.",
    },
    "okx": {
        "label": "OKX",
        "requires_passphrase": True,
        "note": "Under API. Read-only permission only.",
    },
}


@dataclass
class SyncedBalance:
    """One non-zero balance returned from a fetch_balance call."""
    symbol: str            # 'BTC', 'ETH', etc.
    quantity: float


@dataclass
class SyncResult:
    """Outcome of one sync run for one connection."""
    ok: bool
    balances: list[SyncedBalance]
    error: Optional[str] = None


def _sanitize(err: str, secrets: list[str]) -> str:
    """Strip any accidental substring match against a plaintext secret."""
    out = err
    for s in secrets:
        if s and len(s) > 6 and s in out:
            out = out.replace(s, "[redacted]")
    return out


def _make_exchange(
    exchange_id: str,
    api_key: str,
    api_secret: str,
    passphrase: Optional[str] = None,
) -> ccxt.Exchange:
    """Construct a CCXT exchange client. Raises ccxt.NotSupported on unknown id."""
    if exchange_id not in ccxt.exchanges:
        raise ValueError(f"Unknown CCXT exchange id: {exchange_id}")
    cls = getattr(ccxt, exchange_id)
    cfg: dict = {"apiKey": api_key, "secret": api_secret, "enableRateLimit": True}
    if passphrase:
        cfg["password"] = passphrase  # CCXT convention: passphrase → 'password'
    return cls(cfg)


def test_connection(
    exchange_id: str,
    api_key: str,
    api_secret: str,
    passphrase: Optional[str] = None,
) -> SyncResult:
    """Attempt a real fetch_balance with plaintext credentials. Never stores
    them — the caller decides whether to persist based on the outcome."""
    try:
        ex = _make_exchange(exchange_id, api_key, api_secret, passphrase)
        raw = ex.fetch_balance()
    except ccxt.AuthenticationError as e:
        return SyncResult(ok=False, balances=[], error=_sanitize(
            f"Authentication failed — check the API key and secret. ({e})",
            [api_key, api_secret, passphrase or ""],
        ))
    except ccxt.PermissionDenied as e:
        return SyncResult(ok=False, balances=[], error=_sanitize(
            f"Permission denied. The key needs 'view' / 'read' scope. ({e})",
            [api_key, api_secret, passphrase or ""],
        ))
    except ccxt.NetworkError as e:
        return SyncResult(ok=False, balances=[], error=_sanitize(
            f"Exchange unreachable. Try again later. ({e})",
            [api_key, api_secret, passphrase or ""],
        ))
    except Exception as e:
        return SyncResult(ok=False, balances=[], error=_sanitize(
            f"Unexpected error: {e}",
            [api_key, api_secret, passphrase or ""],
        ))

    balances: list[SyncedBalance] = []
    # CCXT normalized balance: {'BTC': {'free': X, 'used': Y, 'total': Z}, ...}
    # Plus 'free', 'used', 'total' top-level dicts, which we skip.
    for sym, info in raw.items():
        if not isinstance(info, dict):
            continue
        if sym in ("free", "used", "total", "info", "timestamp", "datetime"):
            continue
        total = info.get("total") or 0.0
        if total > 0.00000001:
            balances.append(SyncedBalance(symbol=sym.upper(), quantity=float(total)))
    return SyncResult(ok=True, balances=balances)


def sync_connection(
    connection_id: int,
    exchange_id: str,
    api_key_encrypted: str,
    api_secret_encrypted: str,
    passphrase_encrypted: Optional[str] = None,
) -> SyncResult:
    """Decrypt keys and fetch balances for one stored connection."""
    api_key = decrypt_token(api_key_encrypted)
    api_secret = decrypt_token(api_secret_encrypted)
    passphrase = (
        decrypt_token(passphrase_encrypted) if passphrase_encrypted else None
    )
    result = test_connection(exchange_id, api_key, api_secret, passphrase)
    log.info(
        "ccxt sync: connection=%s exchange=%s ok=%s balances=%d",
        connection_id, exchange_id, result.ok, len(result.balances),
    )
    return result
