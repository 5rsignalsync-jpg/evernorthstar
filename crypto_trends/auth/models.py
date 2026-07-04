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
    # Phase 1C: opt-in for the AI-generated morning digest email. Default OFF
    # so we never email someone who didn't ask. Toggled from /account.
    daily_digest_opt_in: bool = Field(default=False, index=True)
    daily_digest_last_sent_at: Optional[datetime] = None


class AlertRule(SQLModel, table=True):
    """A user-defined trigger: 'email me when AAPL momentum_v1 score > 0.6'.

    condition values:
      'score_above'  — momentum_v1 score > threshold
      'score_below'  — momentum_v1 score < threshold
      'price_above'  — latest ohlcv close > threshold (absolute price)
      'price_below'  — latest ohlcv close < threshold
      'zone_target'  — extremum zone for the symbol equals `zone_target`.
                       In this mode `threshold` is unused; the target zone
                       lives in the `zone_target` column.

    Cooldown: a rule won't re-trigger within 6h to prevent spam. Free tier
    limited to 3 active rules, Pro unlimited.
    """
    __tablename__ = "alert_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    symbol: str = Field(index=True)
    asset_class: str
    condition: str          # see docstring
    threshold: float
    # Optional target zone for the 'zone_target' condition. One of
    # ('accumulation', 'distribution', 'extreme_distribution'). Ignored
    # for score_* / price_* conditions.
    zone_target: Optional[str] = None
    enabled: bool = Field(default=True, index=True)
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_triggered_at: Optional[datetime] = None


class AlertEvent(SQLModel, table=True):
    """Append-only history of when each rule fired. Useful for the user to
    review past triggers and for us to debug 'I never got an alert' reports."""
    __tablename__ = "alert_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="alert_rules.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    triggered_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    observed_value: float    # the score or price that caused the fire
    email_sent: bool = False


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
