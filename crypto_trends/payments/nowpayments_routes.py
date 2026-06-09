"""NOWPayments crypto checkout + IPN webhook.

NOWPayments is custodial — they generate per-invoice deposit addresses for
each supported coin (BTC, ETH, SOL, XRP, XLM, HBAR + 200 more), the customer
pays, NOWPayments auto-settles to our payout wallet, and they fire an IPN
webhook back to us when the payment confirms on-chain.

Flow:
  1. Authed user POSTs /billing/checkout-crypto with {plan: "monthly"|"annual"}.
  2. We create a NOWPayments invoice with price_amount in USD; customer picks
     their coin on the hosted page.
  3. NOWPayments redirects them through a hosted checkout that shows the
     deposit address + QR code per chosen coin.
  4. On confirmation, NOWPayments POSTs to /webhooks/nowpayments with an HMAC
     signature in the `x-nowpayments-sig` header.
  5. We verify the sig, look up the user via order_id (we set it to our user.id),
     and extend their subscription.

Unlike Stripe's recurring subscriptions, NOWPayments is one-shot per invoice —
each monthly renewal requires a new invoice. We extend `subscription_expires_at`
by 30 or 365 days on confirmed payment; user needs to pay again before that.
"""

from __future__ import annotations

import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from hashlib import sha512
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from crypto_trends.auth.db import get_session
from crypto_trends.auth.deps import require_user
from crypto_trends.auth.models import PaymentEvent, User
from crypto_trends.config import settings

log = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])

NOWPAYMENTS_BASE = "https://api.nowpayments.io/v1"

# 5% discount for stablecoin-paid plans (incentivize FX-neutral settlement).
STABLECOIN_DISCOUNT = 0.05


class CryptoCheckoutRequest(BaseModel):
    plan: str   # "monthly" | "annual"


class CryptoCheckoutResponse(BaseModel):
    invoice_id: str
    url: str


def _amount_usd(plan: str) -> float:
    if plan == "monthly":
        return 19.00
    if plan == "annual":
        return 190.00
    raise HTTPException(400, f"Unknown plan: {plan}")


def _description(plan: str) -> str:
    period = "month" if plan == "monthly" else "year"
    return f"TheEverNorthstar Pro — {plan} subscription ({period})"


@router.post("/billing/checkout-crypto", response_model=CryptoCheckoutResponse)
def create_crypto_invoice(
    body: CryptoCheckoutRequest,
    user: User = Depends(require_user),
) -> CryptoCheckoutResponse:
    if not settings.nowpayments_api_key:
        raise HTTPException(
            503,
            "Crypto payments are not configured on this deployment. "
            "NOWPayments API key not set.",
        )

    amount = _amount_usd(body.plan)
    base_url = settings.app_base_url.rstrip("/")

    payload = {
        "price_amount": amount,
        "price_currency": "usd",
        # order_id carries our user.id + plan so the webhook can route the payment.
        "order_id": f"u{user.id}_{body.plan}_{int(datetime.utcnow().timestamp())}",
        "order_description": _description(body.plan),
        "ipn_callback_url": f"{base_url.replace(':3000', ':8000')}/webhooks/nowpayments",
        "success_url": f"{base_url}/billing/success?provider=nowpayments",
        "cancel_url": f"{base_url}/pricing?canceled=1",
    }

    try:
        r = httpx.post(
            f"{NOWPAYMENTS_BASE}/invoice",
            headers={"x-api-key": settings.nowpayments_api_key,
                     "Content-Type": "application/json"},
            json=payload,
            timeout=20.0,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.exception("NOWPayments invoice creation failed for user %s", user.id)
        raise HTTPException(502, f"NOWPayments error: {e}")

    data = r.json()
    invoice_id = str(data.get("id") or data.get("invoice_id") or "")
    url = data.get("invoice_url") or data.get("hosted_url")
    if not invoice_id or not url:
        log.error("Unexpected NOWPayments response shape: %s", data)
        raise HTTPException(502, "NOWPayments returned an unexpected response.")

    return CryptoCheckoutResponse(invoice_id=invoice_id, url=url)


def _verify_ipn_signature(raw_body: bytes, sig: str) -> bool:
    """NOWPayments signs the IPN payload with HMAC-SHA512 keyed by IPN_SECRET.

    The signature covers the JSON body with keys sorted alphabetically. Spec at
    https://documenter.getpostman.com/view/7907941/2s93JusNJt — "IPN".
    """
    if not settings.nowpayments_ipn_secret or not sig:
        return False
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return False
    sorted_body = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    digest = hmac.new(
        settings.nowpayments_ipn_secret.encode("utf-8"),
        sorted_body.encode("utf-8"),
        sha512,
    ).hexdigest()
    return hmac.compare_digest(digest, sig.lower())


@router.post("/webhooks/nowpayments")
async def nowpayments_webhook(
    request: Request,
    x_nowpayments_sig: Optional[str] = Header(default=None,
                                              alias="x-nowpayments-sig"),
    session: Session = Depends(get_session),
) -> dict:
    payload = await request.body()

    if not _verify_ipn_signature(payload, x_nowpayments_sig or ""):
        log.warning("NOWPayments webhook with bad signature")
        raise HTTPException(400, "Invalid IPN signature")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON body")

    payment_status = event.get("payment_status", "")
    order_id = event.get("order_id", "")
    log.info("nowpayments ipn: %s order_id=%s", payment_status, order_id)

    # Parse our order_id: "u<user_id>_<plan>_<ts>"
    user = _user_from_order_id(session, order_id)
    if user is None:
        log.warning("nowpayments ipn: could not resolve user from order_id=%s",
                    order_id)
        return {"received": True}

    _record_ipn(session, user.id, event)

    # Only "finished" / "confirmed" extend the subscription.
    if payment_status in ("finished", "confirmed"):
        plan = _plan_from_order_id(order_id)
        days = 365 if plan == "annual" else 30
        new_expiry = (datetime.utcnow() + timedelta(days=days))
        # Stack on top of existing Pro time if they re-up early
        if (user.subscription_expires_at
                and user.subscription_expires_at > datetime.utcnow()):
            new_expiry = user.subscription_expires_at + timedelta(days=days)
        user.subscription_tier = "pro"
        user.subscription_expires_at = new_expiry
        session.add(user)
        session.commit()
        log.info("nowpayments → user %s extended to %s", user.id, new_expiry)

    return {"received": True}


def _user_from_order_id(session: Session, order_id: str) -> Optional[User]:
    """order_id format: "u<int_id>_<plan>_<ts>"."""
    if not order_id.startswith("u"):
        return None
    try:
        user_id = int(order_id[1:].split("_", 1)[0])
    except (ValueError, IndexError):
        return None
    return session.get(User, user_id)


def _plan_from_order_id(order_id: str) -> str:
    """Extract plan from "u<id>_<plan>_<ts>"."""
    parts = order_id.split("_")
    return parts[1] if len(parts) >= 2 else "monthly"


def _record_ipn(session: Session, user_id: int, event: dict) -> None:
    # Idempotency: NOWPayments sends payment_id; use that as the event id.
    event_id = str(event.get("payment_id") or event.get("invoice_id") or "")
    if not event_id:
        return
    from sqlmodel import select
    existing = session.exec(
        select(PaymentEvent).where(PaymentEvent.provider_event_id == event_id)
    ).first()
    if existing:
        return

    # NOWPayments amounts come back as USD-equivalent on the price_amount field;
    # the actual crypto amount is in pay_amount.
    amount_usd = event.get("price_amount") or event.get("actually_paid")
    amount_cents = int(float(amount_usd) * 100) if amount_usd is not None else None

    session.add(PaymentEvent(
        user_id=user_id,
        provider="nowpayments",
        provider_event_id=event_id,
        event_type=f"ipn.{event.get('payment_status', 'unknown')}",
        amount_cents=amount_cents,
        currency=event.get("price_currency") or event.get("pay_currency"),
        raw_payload=json.dumps(event)[:8000],
    ))
    session.commit()
