"""Tier-aware limits — the single source of truth for what Free vs Pro can see.

Philosophy: free users see *all the same surfaces* as Pro (every tab, every
strategy card, drill-down works) but with smaller windows and a visible
"Upgrade to see X" call to the action. Wide-and-shallow > narrow-and-blocked
for trial-to-paid conversion.

Server-side enforcement only. The frontend reflects the limits but the API
clamps them — never trust the client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from crypto_trends.auth.models import User
from crypto_trends.auth.deps import is_pro


@dataclass(frozen=True)
class TierLimits:
    top_n: int                   # max longs / shorts per ranking table
    strategy_positions: int      # max positions shown in strategy detail
    history_headlines: int       # max headlines on /history drill-down
    history_days: int            # max lookback days on /history
    watchlist_max: int           # client-side cap; also surfaced to UI
    csv_export: bool             # /rankings.csv allowed?
    realtime_refresh: bool       # whether the client can poll faster than 5 min
    tier_name: str               # human-readable label for the UI


FREE = TierLimits(
    top_n=3,
    strategy_positions=3,
    history_headlines=5,
    history_days=30,
    watchlist_max=5,
    csv_export=False,
    realtime_refresh=False,
    tier_name="free",
)

# Public limits exposed to the frontend so the client can enforce them
# eagerly (watchlist size, etc.) — server still re-checks.
FREE_WATCHLIST_MAX = FREE.watchlist_max
PRO_WATCHLIST_MAX = PRO.watchlist_max if False else 10_000  # placeholder

PRO = TierLimits(
    top_n=25,
    strategy_positions=50,
    history_headlines=30,
    history_days=730,
    watchlist_max=10_000,
    csv_export=True,
    realtime_refresh=True,
    tier_name="pro",
)


def limits_for(user: Optional[User]) -> TierLimits:
    """The TierLimits the request should be clamped to."""
    return PRO if is_pro(user) else FREE
