"""Curated 'follow-the-personality' strategy presets.

Each preset is an Autopilot-style portfolio recipe: a slug + display metadata +
the filters needed to materialize a basket from the `smart_money_trades` table.

Three flavors:
  - `actor_id` strategies: mirror one actor's book (Buffett, Burry, Ackman, …).
  - `composite` strategies: combine multiple actors' books (quant-consensus).
  - `query` strategies: filter raw smart_money_trades by source/side/amount
    (CEO conviction = insider buys > $1M; insider-selling-alert = sells > $5M).

`inverse=True` flips the implied direction — the basket is shown as positions to
*avoid* / short, and suggested allocations are negative.

`gated_on` blocks the strategy from being recommended until a data source is
wired (e.g., Pelosi needs the Congress ingester live).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Strategy:
    slug: str
    name: str
    emoji: str
    description: str
    caveats: list[str] = field(default_factory=list)

    # Sourcing — exactly one of these patterns is filled in
    actor_id: str | None = None              # single-actor strategies
    actor_ids: list[str] = field(default_factory=list)  # composite strategies
    query_source: str | None = None          # raw query strategies: 'insider'
    query_side: str | None = None            # 'buy' | 'sell'
    query_min_amount: float | None = None    # dollars
    query_max_amount: float | None = None
    query_window_days: int = 30
    query_exclude_10b5_1: bool = True

    # Behavior
    inverse: bool = False
    long_only: bool = True                   # most retail-followable strategies are
    gated_on: str | None = None              # human-readable gate, if any


STRATEGIES: list[Strategy] = [
    Strategy(
        slug="burry-bets",
        name="Burry Bets",
        emoji="🎯",
        actor_id="cik_0001656456",
        description=(
            "Michael Burry's Scion Asset Management — concentrated, contrarian. "
            "Famous from 'The Big Short.'"
        ),
        caveats=[
            "13F covers long equity only — Burry's known short bets (via puts) don't appear here",
            "Quarterly data, 45-day disclosure lag",
        ],
    ),
    Strategy(
        slug="buffett-watcher",
        name="Buffett Watcher",
        emoji="💰",
        actor_id="cik_0001067983",
        description=(
            "Warren Buffett's Berkshire Hathaway — concentrated value, very long holding periods."
        ),
        caveats=[
            "Reflects Berkshire's public equity book only — wholly-owned subsidiaries not visible",
            "Quarterly, 45-day lag",
        ],
    ),
    Strategy(
        slug="ackman-concentrated",
        name="Ackman's Concentrated Book",
        emoji="🎰",
        actor_id="cik_0001336528",
        description=(
            "Bill Ackman's Pershing Square — typically ~10 high-conviction long positions. "
            "Concentrated portfolio, activist-investor history."
        ),
        caveats=["13F doesn't show Ackman's hedges (notably his macro CDS trades)", "45-day lag"],
    ),
    Strategy(
        slug="ark-innovation",
        name="ARK Innovation",
        emoji="🚀",
        actor_id="cik_0001603466",
        description=(
            "Cathie Wood's ARK Investment Management — high-growth, disruptive-tech focus. "
            "Volatile sector tilts."
        ),
        caveats=["Track record is mixed since 2021 — high-beta exposure", "Quarterly + 45-day lag"],
    ),
    Strategy(
        slug="soros-plays",
        name="Soros Plays",
        emoji="🌶️",
        actor_id="cik_0001029160",
        description="Soros Fund Management — macro-driven, opportunistic positions across sectors.",
        caveats=["Trades on macro views; 13F snapshot may lag the actual thesis"],
    ),
    Strategy(
        slug="quant-consensus",
        name="Quant Consensus",
        emoji="🧠",
        actor_ids=["cik_0001037389", "cik_0001423053", "cik_0001167483"],  # RenTec, Citadel, Tudor
        description=(
            "Names held by ≥2 of {Renaissance Technologies, Citadel, Tudor Investment} — "
            "the most disciplined quant + global-macro shops."
        ),
        caveats=[
            "Quant books have very high turnover; quarterly 13F is a stale snapshot",
            "Names may already have rolled off by the time you'd buy them",
        ],
    ),
    Strategy(
        slug="ceo-conviction",
        name="CEO Conviction Buys",
        emoji="💼",
        query_source="insider",
        query_side="buy",
        query_min_amount=1_000_000.0,
        query_window_days=30,
        description=(
            "Recent Form 4 insider purchases of $1M+ — insiders rarely buy without a reason. "
            "Sales are noisier and excluded."
        ),
        caveats=[
            "Aggregates all officers/directors — not just CEO",
            "Some 'buys' are option exercises with conversion code A — surface code in detail view",
        ],
    ),
    Strategy(
        slug="insider-selling-alert",
        name="Insider Selling Alert",
        emoji="🚨",
        query_source="insider",
        query_side="sell",
        query_min_amount=5_000_000.0,
        query_window_days=30,
        inverse=True,
        description=(
            "Recent Form 4 insider sales of $5M+. Excludes 10b5-1 programmed sales "
            "where flagged. Treat as a 'be careful' filter, not necessarily a short signal."
        ),
        caveats=[
            "10b5-1 plan sales aren't perfectly tagged in EDGAR; some leak through",
            "Sales for diversification ≠ bearish view",
        ],
    ),
    Strategy(
        slug="pelosi-tracker",
        name="Pelosi Tracker",
        emoji="🦅",
        # Deterministic actor_id format from congress.py ingester:
        # f"congress_{chamber}_{lastname}_{firstname}" all lowercased.
        actor_id="congress_house_pelosi_nancy",
        description=(
            "Nancy Pelosi's disclosed STOCK Act trades. 45-day legal lag; "
            "research shows mixed performance, much of it from tech-exposure timing."
        ),
        caveats=[
            "Position sizes are reported as dollar ranges, not exact amounts",
            "45-day lag is the legal max; some filings come later still",
            "Outperformance signal is contested in recent academic work",
            "FMP free tier only returns the 25 most-recent House disclosures — "
            "Pelosi-specific history requires the $14/mo Starter tier",
        ],
    ),
    Strategy(
        slug="kongressional-conviction",
        name="Kongressional Conviction",
        emoji="🏛️",
        query_source="congress%",   # SQL LIKE — matches congress_senate + congress_house
        query_side="buy",
        query_window_days=60,
        description=(
            "Top tickers bought across all of Congress in the most recent disclosures. "
            "Aggregates breadth across members — even on FMP free (25 trades per chamber)."
        ),
        caveats=[
            "Free tier shows only the most recent ~25 trades per chamber",
            "Position sizes are dollar ranges, not exact amounts — totals are bracket midpoints",
            "45-day disclosure lag is built in (legal max under STOCK Act)",
        ],
    ),
]


def by_slug(slug: str) -> Strategy | None:
    for s in STRATEGIES:
        if s.slug == slug:
            return s
    return None
