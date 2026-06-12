"""Thin Resend wrapper for outbound transactional email.

Gated on settings.resend_api_key — when empty, send() returns False instead
of crashing. This lets us deploy the daily-digest pipeline before provisioning
the Resend account, then flip on by setting one env var.

Resend free tier = 3k emails/month, plenty for early users.
"""

from __future__ import annotations

import logging
from typing import Optional

from crypto_trends.config import settings

log = logging.getLogger(__name__)

_resend_module = None


def _get_resend():
    global _resend_module
    if _resend_module is not None:
        return _resend_module
    if not settings.resend_api_key:
        return None
    try:
        import resend
        resend.api_key = settings.resend_api_key
        _resend_module = resend
        return _resend_module
    except ImportError:
        log.error("resend SDK not installed; pip install resend")
        return None


def send(
    to: str,
    subject: str,
    html: str,
    text: Optional[str] = None,
    from_email: Optional[str] = None,
) -> bool:
    """Send a transactional email. Returns True on success, False if disabled
    or the call failed. Logs failures rather than raising so a single bad
    address doesn't kill a digest batch."""
    resend_mod = _get_resend()
    if resend_mod is None:
        log.info("email send skipped (resend not configured): to=%s subj=%r", to, subject)
        return False
    try:
        params: dict = {
            "from": from_email or settings.digest_from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if text:
            params["text"] = text
        resend_mod.Emails.send(params)
        return True
    except Exception as e:
        log.exception("email send failed to=%s: %s", to, e)
        return False


def is_enabled() -> bool:
    return bool(settings.resend_api_key)
