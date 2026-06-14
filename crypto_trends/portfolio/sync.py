"""Holdings sync — fetch fresh positions from Plaid and persist them.

Pattern: DELETE all holdings for an account, then INSERT the fresh batch.
This is simpler than reconcile-by-diff and avoids stale-position bugs.
Plaid holdings updates only after the brokerage reports them (T+1 typical).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlmodel import Session, delete, select

from crypto_trends.auth import db as auth_db
from crypto_trends.portfolio import plaid_client
from crypto_trends.portfolio.encryption import decrypt_token
from crypto_trends.portfolio.models import BrokerageAccount, Holding

log = logging.getLogger(__name__)


def sync_account(account_id: int) -> dict:
    """Sync one BrokerageAccount. Returns counters for logging.

    Failure modes:
      - Plaid not configured → raises PlaidUnavailable (caller decides)
      - access token decrypt fails → marks account 'error' with last_error
      - Plaid API error → marks account 'error', records exception message,
        does NOT delete existing holdings (preserves last-known-good state)
    """
    with Session(auth_db._engine) as session:
        account = session.get(BrokerageAccount, account_id)
        if account is None:
            return {"status": "not_found"}

        try:
            access_token = decrypt_token(account.access_token_encrypted)
        except Exception as e:
            account.status = "error"
            account.last_error = f"decrypt failed: {e}"
            session.add(account); session.commit()
            log.exception("decrypt failed for account %d", account_id)
            return {"status": "decrypt_error"}

        try:
            holdings = plaid_client.fetch_holdings(access_token)
        except Exception as e:
            account.status = "error"
            account.last_error = str(e)[:500]
            session.add(account); session.commit()
            log.exception("plaid fetch failed for account %d", account_id)
            return {"status": "plaid_error", "error": str(e)}

        # Wipe + reinsert. This intentionally drops holdings the brokerage no
        # longer reports (sold positions) which is the behavior users expect.
        session.exec(delete(Holding).where(Holding.account_id == account_id))
        now = datetime.utcnow().replace(tzinfo=None)
        for h in holdings:
            session.add(Holding(
                account_id=account_id,
                user_id=account.user_id,
                ticker=h.ticker,
                name=h.name,
                security_type=h.security_type,
                quantity=h.quantity,
                price=h.price,
                value=h.value,
                cost_basis=h.cost_basis,
                iso_currency_code=h.iso_currency_code,
                synced_at=now,
            ))
        account.status = "active"
        account.last_error = None
        account.last_synced_at = now
        session.add(account)
        session.commit()
        return {"status": "ok", "holdings_count": len(holdings)}


def sync_all_active_accounts() -> dict:
    """Sync every active brokerage account. Called by the daily cron.
    Failures on individual accounts do NOT halt the batch."""
    if not plaid_client.is_enabled():
        log.warning("plaid not configured — sync skipped")
        return {"status": "disabled"}

    with Session(auth_db._engine) as session:
        rows = session.exec(
            select(BrokerageAccount.id).where(BrokerageAccount.status == "active")
        ).all()
        ids = [r for r in rows]

    log.info("syncing %d active brokerage accounts", len(ids))
    summary = {"total": len(ids), "ok": 0, "errors": 0}
    for aid in ids:
        result = sync_account(aid)
        if result.get("status") == "ok":
            summary["ok"] += 1
        else:
            summary["errors"] += 1
    log.info("sync done: %s", summary)
    return summary
