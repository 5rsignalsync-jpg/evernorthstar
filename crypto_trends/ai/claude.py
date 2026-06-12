"""Thin Anthropic Claude wrapper for AI features.

Gated on settings.anthropic_api_key — when empty, calls return None and the
endpoint surfaces a friendly 503 'feature pending' message instead of a
crash. This lets us deploy the AI features fully wired up before the user
provisions their API key, then flip on by setting one env var.

Uses the Messages API + the Anthropic Python SDK.
"""

from __future__ import annotations

import logging
from typing import Optional

from crypto_trends.config import settings

log = logging.getLogger(__name__)

# Lazy-imported. anthropic sdk is in pyproject deps but we don't want to
# pay the import cost on app boot if AI is disabled.
_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return _client
    except ImportError:
        log.error("anthropic SDK not installed; pip install anthropic")
        return None


def ask(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    model: Optional[str] = None,
) -> Optional[str]:
    """Synchronous Claude call. Returns the text response, or None if the
    feature is disabled (no API key) or the call failed. Caller decides
    how to surface None (usually a 503)."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=model or settings.anthropic_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # resp.content is a list of blocks; concatenate any text blocks
        parts: list[str] = []
        for block in resp.content:
            if getattr(block, "type", "") == "text":
                parts.append(getattr(block, "text", ""))
        return "".join(parts).strip() or None
    except Exception as e:
        log.exception("Claude call failed: %s", e)
        return None


def is_enabled() -> bool:
    """Cheap check — used by endpoints to gate feature availability."""
    return bool(settings.anthropic_api_key)
