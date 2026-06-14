"""Plaid SDK wrapper for EverNorthstar.

Handles env switching (sandbox/development/production), Link token creation,
public token exchange, and holdings fetch. Returns plain dicts/dataclasses
so the rest of the app stays Plaid-agnostic — if we ever swap providers
(Yodlee, Finicity), only this module changes.

All methods raise PlaidUnavailable when settings.plaid_client_id is empty
so endpoints can surface a clean 'feature pending' 503 instead of crashing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from crypto_trends.config import settings

log = logging.getLogger(__name__)

# Lazy-init so app boot doesn't pay the Plaid SDK import cost when feature
# is disabled (no client_id).
_plaid_client = None


class PlaidUnavailable(Exception):
    """Raised when Plaid credentials aren't configured."""


def _env_url() -> str:
    """Map our env string to Plaid's actual API URL."""
    return {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }.get(settings.plaid_env, "https://sandbox.plaid.com")


def _get_client():
    global _plaid_client
    if _plaid_client is not None:
        return _plaid_client
    if not settings.plaid_client_id or not settings.plaid_secret:
        raise PlaidUnavailable(
            "Plaid credentials not configured. Set PLAID_CLIENT_ID and "
            "PLAID_SECRET via env or Fly secrets."
        )
    import plaid
    from plaid.api import plaid_api

    configuration = plaid.Configuration(
        host=_env_url(),
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )
    api_client = plaid.ApiClient(configuration)
    _plaid_client = plaid_api.PlaidApi(api_client)
    return _plaid_client


def is_enabled() -> bool:
    return bool(settings.plaid_client_id and settings.plaid_secret)


# ---------------- Link token + token exchange ----------------

def create_link_token(user_id: int, user_email: str) -> str:
    """Create a one-time link token for the frontend's Plaid Link modal."""
    client = _get_client()
    from plaid.model.country_code import CountryCode
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.products import Products

    products = [Products(p.strip()) for p in settings.plaid_products.split(",") if p.strip()]
    countries = [CountryCode(c.strip()) for c in settings.plaid_country_codes.split(",") if c.strip()]

    req = LinkTokenCreateRequest(
        products=products,
        client_name="EverNorthstar",
        country_codes=countries,
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
    )
    resp = client.link_token_create(req)
    return resp["link_token"]


@dataclass
class ExchangedItem:
    """Result of exchanging a public token. Persist this to BrokerageAccount."""
    item_id: str
    access_token: str
    institution_id: Optional[str]
    institution_name: str


def exchange_public_token(public_token: str) -> ExchangedItem:
    """Exchange the short-lived public_token from Plaid Link for a long-lived
    access_token + item_id. Also fetches institution name in the same call so
    we have something user-friendly to show."""
    client = _get_client()
    from plaid.model.item_get_request import ItemGetRequest
    from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
    from plaid.model.country_code import CountryCode
    from plaid.model.item_public_token_exchange_request import (
        ItemPublicTokenExchangeRequest,
    )

    exchange_resp = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=public_token)
    )
    access_token = exchange_resp["access_token"]
    item_id = exchange_resp["item_id"]

    # Look up institution_id + name. This is two API calls; we could let
    # the frontend pass institution metadata to save one, but the server-side
    # call is authoritative.
    item_resp = client.item_get(ItemGetRequest(access_token=access_token))
    institution_id = item_resp["item"].get("institution_id")

    institution_name = "Unknown"
    if institution_id:
        countries = [CountryCode(c.strip()) for c in settings.plaid_country_codes.split(",") if c.strip()]
        inst_resp = client.institutions_get_by_id(
            InstitutionsGetByIdRequest(
                institution_id=institution_id, country_codes=countries
            )
        )
        institution_name = inst_resp["institution"]["name"]

    return ExchangedItem(
        item_id=item_id,
        access_token=access_token,
        institution_id=institution_id,
        institution_name=institution_name,
    )


# ---------------- Holdings ----------------

@dataclass
class PlaidHolding:
    """Normalized holding from Plaid /investments/holdings/get."""
    ticker: Optional[str]
    name: str
    security_type: Optional[str]
    quantity: float
    price: Optional[float]
    value: Optional[float]
    cost_basis: Optional[float]
    iso_currency_code: str


def fetch_holdings(access_token: str) -> list[PlaidHolding]:
    """Pull all holdings across all sub-accounts for a brokerage item.

    Plaid's response splits holdings (per-account-per-security) from securities
    (the company metadata). We join them by security_id.
    """
    client = _get_client()
    from plaid.model.investments_holdings_get_request import (
        InvestmentsHoldingsGetRequest,
    )

    resp = client.investments_holdings_get(
        InvestmentsHoldingsGetRequest(access_token=access_token)
    )
    holdings = resp.get("holdings", [])
    securities = {s["security_id"]: s for s in resp.get("securities", [])}

    out: list[PlaidHolding] = []
    for h in holdings:
        sec = securities.get(h["security_id"], {})
        ticker = sec.get("ticker_symbol")
        # Sandbox / some funds return None for ticker but have a name
        name = sec.get("name") or ticker or "Unknown security"
        sec_type = sec.get("type")  # 'equity' | 'etf' | 'mutual fund' | 'cash' | ...

        out.append(PlaidHolding(
            ticker=ticker.upper() if isinstance(ticker, str) else None,
            name=name,
            security_type=sec_type,
            quantity=float(h.get("quantity") or 0),
            price=float(h["institution_price"]) if h.get("institution_price") is not None else None,
            value=float(h["institution_value"]) if h.get("institution_value") is not None else None,
            cost_basis=float(h["cost_basis"]) if h.get("cost_basis") is not None else None,
            iso_currency_code=h.get("iso_currency_code") or "USD",
        ))
    return out


def remove_item(access_token: str) -> None:
    """Revoke a Plaid item — call when the user disconnects a brokerage."""
    client = _get_client()
    from plaid.model.item_remove_request import ItemRemoveRequest

    try:
        client.item_remove(ItemRemoveRequest(access_token=access_token))
    except Exception as e:
        # Plaid will sometimes return 'ITEM_NOT_FOUND' if already removed.
        # That's fine — we're being defensive.
        log.warning("plaid item_remove failed (likely already gone): %s", e)
