"""Stripe checkout + webhook routes.

Flow:
  1. Logged-in user POSTs /billing/checkout-session with {plan: "monthly"|"annual"}.
  2. We create a Stripe Checkout Session (client_reference_id = our user.id)
     and return the hosted URL.
  3. User completes checkout in Stripe-hosted flow.
  4. Stripe POSTs /webhooks/stripe with the event. We verify the signature,
     look up the user via client_reference_id, and update their subscription
     fields.

Webhook signing secret comes from `stripe listen --print-secret` (local dev)
or from the dashboard's webhook config (prod). Both end up in STRIPE_WEBHOOK_SECRET.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from crypto_trends.auth.db import get_session
from crypto_trends.auth.deps import require_user
from crypto_trends.auth.models import PaymentEvent, User
from crypto_trends.config import settings

log = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])

stripe.api_key = settings.stripe_secret_key


class CheckoutRequest(BaseModel):
    plan: str   # "monthly" | "annual"


class CheckoutResponse(BaseModel):
    url: str
    session_id: str


class PortalResponse(BaseModel):
    url: str


def _price_id(plan: str) -> str:
    if plan == "monthly":
        return settings.stripe_price_pro_monthly
    if plan == "annual":
        return settings.stripe_price_pro_annual
    raise HTTPException(400, f"Unknown plan: {plan}")


@router.post("/billing/checkout-session", response_model=CheckoutResponse)
def create_checkout_session(
    body: CheckoutRequest,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> CheckoutResponse:
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Stripe is not configured on this deployment.")

    price = _price_id(body.plan)
    if not price:
        raise HTTPException(503, f"No price ID configured for plan: {body.plan}")

    # Reuse the same Stripe customer if we've seen this user before;
    # otherwise let Checkout create one and we'll capture the ID via webhook.
    customer_id = user.stripe_customer_id

    base_url = settings.app_base_url.rstrip("/")
    try:
        sess = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price, "quantity": 1}],
            success_url=f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/pricing?canceled=1",
            client_reference_id=str(user.id),
            customer=customer_id or None,
            customer_email=user.email if not customer_id else None,
            allow_promotion_codes=True,
            metadata={"user_id": str(user.id), "plan": body.plan},
        )
    except stripe.StripeError as e:
        log.exception("Stripe checkout session creation failed for user %s", user.id)
        raise HTTPException(502, f"Stripe error: {e.user_message or str(e)}")

    return CheckoutResponse(url=sess.url, session_id=sess.id)


class FounderCheckoutResponse(BaseModel):
    url: str
    session_id: str
    spots_remaining: int


@router.get("/billing/founder-spots")
def founder_spots(session: Session = Depends(get_session)) -> dict:
    """How many founder lifetime spots are left? Public — used by the
    pricing page to show 'X of 100 spots remaining' (or hide the button
    when sold out)."""
    sold = session.exec(
        select(User).where(User.subscription_tier == "founder_lifetime")
    ).all()
    return {
        "sold": len(sold),
        "cap": settings.founder_lifetime_spot_cap,
        "remaining": max(0, settings.founder_lifetime_spot_cap - len(sold)),
    }


@router.post("/billing/checkout-founder", response_model=FounderCheckoutResponse)
def create_founder_checkout(
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> FounderCheckoutResponse:
    """One-time $99 payment for Founder Lifetime tier (Pro forever)."""
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Stripe is not configured on this deployment.")
    if not settings.stripe_price_founder_lifetime:
        raise HTTPException(
            503,
            "Founder Lifetime price not configured — set STRIPE_PRICE_FOUNDER_LIFETIME.",
        )

    # Hard cap enforcement.
    sold_count = len(session.exec(
        select(User).where(User.subscription_tier == "founder_lifetime")
    ).all())
    if sold_count >= settings.founder_lifetime_spot_cap:
        raise HTTPException(
            410,  # 410 Gone — feels right for "no longer available"
            f"All {settings.founder_lifetime_spot_cap} founder spots have been claimed. "
            "Subscribe to Pro monthly or annual instead.",
        )

    # Already on this tier? No reason to buy again.
    if user.subscription_tier == "founder_lifetime":
        raise HTTPException(
            409,
            "You already have Founder Lifetime — no further payment needed.",
        )

    customer_id = user.stripe_customer_id
    base_url = settings.app_base_url.rstrip("/")
    try:
        sess = stripe.checkout.Session.create(
            mode="payment",  # one-time, NOT subscription
            line_items=[{"price": settings.stripe_price_founder_lifetime, "quantity": 1}],
            success_url=f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}&plan=founder",
            cancel_url=f"{base_url}/pricing?canceled=1",
            client_reference_id=str(user.id),
            customer=customer_id or None,
            customer_email=user.email if not customer_id else None,
            # The metadata is how the webhook knows to apply the lifetime tier
            # instead of regular Pro. Without it, both buy-Pro and buy-Founder
            # would land as the same tier change.
            metadata={"user_id": str(user.id), "plan": "founder_lifetime"},
            allow_promotion_codes=False,  # No promo codes on the lifetime tier
        )
    except stripe.StripeError as e:
        log.exception("Founder Lifetime checkout session creation failed for user %s", user.id)
        raise HTTPException(502, f"Stripe error: {e.user_message or str(e)}")

    return FounderCheckoutResponse(
        url=sess.url,
        session_id=sess.id,
        spots_remaining=settings.founder_lifetime_spot_cap - sold_count - 1,
    )


@router.post("/billing/portal-session", response_model=PortalResponse)
def create_portal_session(
    user: User = Depends(require_user),
) -> PortalResponse:
    """Stripe-hosted portal where users self-manage their subscription —
    update card, view receipts, cancel. Free users with no stripe_customer_id
    can't access this (we 400 with a useful message)."""
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Stripe is not configured on this deployment.")
    if not user.stripe_customer_id:
        raise HTTPException(
            400,
            "No active subscription found for your account. Subscribe first.",
        )

    base_url = settings.app_base_url.rstrip("/")
    try:
        sess = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{base_url}/account",
        )
    except stripe.StripeError as e:
        log.exception("portal session creation failed for user %s", user.id)
        raise HTTPException(502, f"Stripe error: {e.user_message or str(e)}")
    return PortalResponse(url=sess.url)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
    session: Session = Depends(get_session),
) -> dict:
    payload = await request.body()

    if not settings.stripe_webhook_secret:
        log.error("Stripe webhook hit but STRIPE_WEBHOOK_SECRET is not set")
        raise HTTPException(503, "Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret,
        )
    except stripe.SignatureVerificationError:
        log.warning("Invalid Stripe webhook signature")
        raise HTTPException(400, "Invalid signature")
    except Exception as e:
        log.exception("Webhook parse failed")
        raise HTTPException(400, f"Webhook parse failed: {e}")

    # Convert Stripe's StripeObject → plain dict via JSON round-trip.
    # StripeObject overrides both .get() (AttributeError) and dict() (KeyError)
    # so the safest path is its JSON representation, which we know exists
    # because the webhook payload arrived as JSON in the first place.
    event_dict = json.loads(str(event))
    event_type = event_dict["type"]
    event_id = event_dict.get("id", "unknown")
    obj = event_dict["data"]["object"]

    log.info("stripe webhook: %s id=%s", event_type, event_id)

    user = _user_from_event(session, obj)
    if user is None:
        log.warning("stripe webhook %s: could not resolve user (customer=%s ref=%s)",
                    event_type, obj.get("customer"), obj.get("client_reference_id"))
    else:
        _record_event(session, user.id, event_id, event_type, obj)
        _apply_event(session, user, event_type, obj)

    return {"received": True}


def _user_from_event(session: Session, obj: dict) -> User | None:
    """Resolve our User row from a Stripe event object (plain dict)."""
    # checkout.session.completed carries our user.id in client_reference_id
    ref = obj.get("client_reference_id")
    if ref:
        try:
            user = session.get(User, int(ref))
            if user:
                return user
        except (ValueError, TypeError):
            pass

    # Subsequent invoice / subscription events only have customer ID
    customer_id = obj.get("customer")
    if customer_id:
        return session.exec(
            select(User).where(User.stripe_customer_id == customer_id)
        ).first()
    return None


def _record_event(
    session: Session, user_id: int, event_id: str, event_type: str, obj: dict,
) -> None:
    # Idempotency: don't double-record the same Stripe event ID
    existing = session.exec(
        select(PaymentEvent).where(PaymentEvent.provider_event_id == event_id)
    ).first()
    if existing:
        return

    amount = obj.get("amount_total") or obj.get("amount_paid")
    currency = obj.get("currency")
    session.add(PaymentEvent(
        user_id=user_id,
        provider="stripe",
        provider_event_id=event_id,
        event_type=event_type,
        amount_cents=int(amount) if amount is not None else None,
        currency=currency,
        raw_payload=json.dumps(obj, default=str)[:8000],
    ))
    session.commit()


def _apply_event(session: Session, user: User, event_type: str, obj: dict) -> None:
    """Translate Stripe event into a user-table mutation."""
    changed = False

    if event_type == "checkout.session.completed":
        customer = obj.get("customer")
        if customer and not user.stripe_customer_id:
            user.stripe_customer_id = customer
            changed = True

        # Distinguish founder-lifetime from regular Pro using the metadata we
        # set on session creation. mode='payment' also works as a signal but
        # metadata is explicit.
        metadata = obj.get("metadata") or {}
        is_founder = (
            metadata.get("plan") == "founder_lifetime"
            or obj.get("mode") == "payment"
        )
        if is_founder:
            user.subscription_tier = "founder_lifetime"
            user.subscription_expires_at = None  # Lifetime = no expiry
        else:
            user.subscription_tier = "pro"
        changed = True

    elif event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        status = obj.get("status")
        if status in ("active", "trialing"):
            user.subscription_tier = "pro"
            current_period_end = obj.get("current_period_end")
            if current_period_end:
                user.subscription_expires_at = datetime.fromtimestamp(
                    int(current_period_end), tz=timezone.utc,
                ).replace(tzinfo=None)
            changed = True
        elif status in ("canceled", "incomplete_expired", "unpaid", "past_due"):
            # Don't yank Pro mid-period; let it expire naturally if expires_at is set.
            # For hard cancellations, set expires_at to now.
            if status == "canceled":
                user.subscription_expires_at = datetime.utcnow()
                changed = True

    elif event_type == "customer.subscription.deleted":
        user.subscription_expires_at = datetime.utcnow()
        changed = True

    elif event_type == "invoice.payment_failed":
        # Could send an email here; for now just log
        log.warning("invoice.payment_failed for user=%s customer=%s",
                    user.id, obj.get("customer"))

    if changed:
        session.add(user)
        session.commit()
        log.info("user %s tier=%s expires=%s", user.id,
                 user.subscription_tier, user.subscription_expires_at)
