"""Portfolio domain models — brokerage connections + position snapshots.

A user can connect multiple brokerages (Fidelity, Schwab, Robinhood, etc).
Each connection is one BrokerageAccount row with an encrypted Plaid access
token. Plaid's access tokens are long-lived per-item, so we encrypt them at
rest with Fernet derived from settings.secret_key.

Holdings are SNAPSHOTS, not live state. We refresh them daily via cron.
This is cheaper than per-request Plaid API calls (which we'd otherwise
incur every time the user loads /portfolio) and matches the rest of the
app's daily-refresh cadence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class BrokerageAccount(SQLModel, table=True):
    """A user's connection to one brokerage institution via Plaid.

    One Plaid 'item' = one institution (e.g. Fidelity). An item may contain
    multiple sub-accounts (Roth IRA, brokerage, 401k) but for V1 we treat the
    item as the unit — sub-accounts get rolled up into the same Holdings list.
    """
    __tablename__ = "brokerage_accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    plaid_item_id: str = Field(index=True, unique=True)
    # Fernet-encrypted Plaid access token. NEVER stored in plaintext —
    # access tokens grant ongoing read access to the user's brokerage.
    access_token_encrypted: str
    institution_name: str
    institution_id: Optional[str] = None
    status: str = Field(default="active", index=True)  # 'active' | 'error' | 'disconnected'
    last_synced_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Holding(SQLModel, table=True):
    """A single security position snapshot from a brokerage sync.

    On each sync we DELETE all existing Holdings for the account and INSERT
    fresh ones. This keeps the table simple and avoids stale-position bugs.
    For a history view later, we'll add a separate `HoldingsSnapshot` table.
    """
    __tablename__ = "holdings"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="brokerage_accounts.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    ticker: Optional[str] = Field(default=None, index=True)  # nullable for unknown securities
    name: str   # e.g. "Apple Inc"
    security_type: Optional[str] = None  # 'equity' | 'etf' | 'mutual_fund' | 'cash' | ...
    quantity: float
    price: Optional[float] = None
    value: Optional[float] = None
    cost_basis: Optional[float] = None  # Plaid sometimes returns this
    iso_currency_code: str = "USD"
    synced_at: datetime = Field(default_factory=datetime.utcnow, index=True)
