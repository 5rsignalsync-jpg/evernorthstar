"""User + subscription data model.

Tier is a string enum-ish value: 'free' | 'pro' | 'founder_lifetime'.
Founder lifetime never expires (subscription_expires_at = NULL). Pro expires
based on Stripe billing cycle OR NOWPayments invoice extension.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    subscription_tier: str = Field(default="free", index=True)
    subscription_expires_at: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None


class PaymentEvent(SQLModel, table=True):
    """Append-only ledger of payment events. Source of truth lives at the
    payment provider (Stripe/NOWPayments); this is for our records + reconciling."""
    __tablename__ = "payment_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    provider: str   # 'stripe' | 'nowpayments'
    provider_event_id: str = Field(index=True)
    event_type: str   # e.g. 'invoice.payment_succeeded', 'payment.confirmed'
    amount_cents: Optional[int] = None
    currency: Optional[str] = None
    raw_payload: Optional[str] = None   # JSON string for audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
