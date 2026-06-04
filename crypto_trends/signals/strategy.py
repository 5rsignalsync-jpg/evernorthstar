"""Strategy basket + allocation computation.

Given a Strategy preset, materialize:
  - A weighted basket (dict of ticker → weight in [0, 1])
  - Suggested $ allocations for a chosen portfolio size
  - Recent activity feed (most recent transactions for the strategy)

The weight is value-share: each ticker's value / total basket value. Inverse
strategies negate the weights. Strategies with `gated_on` set return a card
with `ready=False` so the UI can render a CTA instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from crypto_trends.data.store import connect
from crypto_trends.data.strategies import STRATEGIES, Strategy, by_slug


@dataclass
class Position:
    ticker: str
    weight: float           # in [-1, 1]; signed by inverse
    value_usd: float        # raw $ value before normalization
    suggested_usd: float    # weight * portfolio_size
    note: str | None = None


@dataclass
class Activity:
    ticker: str
    actor_name: str
    side: str
    amount_usd: float | None
    disclosure_date: str
    source: str
    note: str | None = None


@dataclass
class StrategyCard:
    slug: str
    name: str
    emoji: str
    description: str
    caveats: list[str]
    ready: bool
    gated_reason: str | None
    n_positions: int
    last_activity: str | None       # ISO date


@dataclass
class StrategyDetail:
    card: StrategyCard
    inverse: bool
    portfolio_size: float
    positions: list[Position]
    recent_activity: list[Activity]


def _fetch_for_strategy(s: Strategy) -> pd.DataFrame:
    """Pull rows from smart_money_trades matching the strategy spec."""
    with connect(read_only=True) as conn:
        if s.actor_id:
            return conn.execute(
                "SELECT ticker, side, amount_min, amount_max, shares, "
                "disclosure_date, actor_name, source, notes "
                "FROM smart_money_trades WHERE actor_id = ?", [s.actor_id],
            ).fetchdf()

        if s.actor_ids:
            placeholders = ",".join("?" * len(s.actor_ids))
            return conn.execute(
                f"SELECT ticker, side, amount_min, amount_max, shares, "
                f"disclosure_date, actor_name, source, notes "
                f"FROM smart_money_trades WHERE actor_id IN ({placeholders})",
                s.actor_ids,
            ).fetchdf()

        if s.query_source:
            # Allow wildcard: query_source="congress%" matches both
            # 'congress_senate' and 'congress_house'.
            op = "LIKE" if "%" in s.query_source else "="
            sql = (
                f"SELECT ticker, side, amount_min, amount_max, shares, "
                f"disclosure_date, actor_name, source, notes "
                f"FROM smart_money_trades WHERE source {op} ?"
            )
            params: list = [s.query_source]
            if s.query_side:
                sql += " AND side = ?"
                params.append(s.query_side)
            if s.query_min_amount is not None:
                sql += " AND amount_min >= ?"
                params.append(s.query_min_amount)
            if s.query_max_amount is not None:
                sql += " AND amount_min <= ?"
                params.append(s.query_max_amount)
            if s.query_window_days:
                cutoff = (datetime.utcnow() - timedelta(days=s.query_window_days)) \
                    .date().isoformat()
                sql += " AND disclosure_date >= ?"
                params.append(cutoff)
            if s.query_exclude_10b5_1:
                sql += " AND (notes IS NULL OR notes NOT LIKE '%10b5-1%')"
            return conn.execute(sql, params).fetchdf()

        return pd.DataFrame()


def _materialize(s: Strategy, portfolio_size: float) -> StrategyDetail:
    df = _fetch_for_strategy(s)

    last_activity = None
    n_positions = 0
    positions: list[Position] = []
    activity: list[Activity] = []

    if not df.empty:
        # For composite strategies, require at least 2 actors per ticker.
        if s.actor_ids:
            counts = df.groupby("ticker")["actor_name"].nunique()
            keep = counts[counts >= 2].index
            df = df[df["ticker"].isin(keep)]

        # Aggregate to per-ticker $ value. For buy/sell strategies, compute net.
        if s.query_side == "sell":
            agg = df.groupby("ticker")["amount_min"].sum()
        else:
            agg = df.groupby("ticker")["amount_min"].sum()
        agg = agg[agg > 0].sort_values(ascending=False)

        if not agg.empty:
            total = agg.sum()
            sign = -1.0 if s.inverse else 1.0
            for ticker, value in agg.items():
                weight_unsigned = float(value / total)
                positions.append(Position(
                    ticker=str(ticker),
                    weight=sign * weight_unsigned,
                    value_usd=float(value),
                    suggested_usd=sign * weight_unsigned * portfolio_size,
                ))

        n_positions = len(positions)
        if "disclosure_date" in df.columns and not df["disclosure_date"].dropna().empty:
            last_activity = str(df["disclosure_date"].max())

        df_sorted = df.sort_values("disclosure_date", ascending=False).head(15)
        for _, row in df_sorted.iterrows():
            activity.append(Activity(
                ticker=str(row["ticker"]),
                actor_name=str(row["actor_name"]),
                side=str(row["side"]),
                amount_usd=float(row["amount_min"]) if pd.notna(row["amount_min"]) else None,
                disclosure_date=str(row["disclosure_date"]),
                source=str(row["source"]),
                note=str(row["notes"]) if pd.notna(row.get("notes")) else None,
            ))

    ready = s.gated_on is None and n_positions > 0
    if s.gated_on:
        gated_reason = s.gated_on
    elif n_positions == 0:
        if s.actor_id:
            # Single-actor strategy with no positions — the ingester ran, this actor
            # just isn't in the data we have access to.
            human = s.actor_id.replace("congress_house_", "").replace(
                "congress_senate_", "").replace("_", " ").title()
            gated_reason = (
                f"{human} has no positions in the data we currently hold. "
                "On FMP free tier we can only fetch the 25 most-recent disclosures "
                "per chamber; this actor isn't in that window. Upgrade to FMP "
                "Starter ($14/mo) for full history."
            )
        else:
            gated_reason = "No data yet — run the smart-money ingester."
    else:
        gated_reason = None

    card = StrategyCard(
        slug=s.slug, name=s.name, emoji=s.emoji,
        description=s.description, caveats=list(s.caveats),
        ready=ready,
        gated_reason=gated_reason,
        n_positions=n_positions,
        last_activity=last_activity,
    )

    return StrategyDetail(
        card=card, inverse=s.inverse, portfolio_size=portfolio_size,
        positions=positions, recent_activity=activity,
    )


def list_cards() -> list[StrategyCard]:
    return [_materialize(s, portfolio_size=10_000.0).card for s in STRATEGIES]


def detail(slug: str, portfolio_size: float = 10_000.0) -> StrategyDetail | None:
    s = by_slug(slug)
    if s is None:
        return None
    return _materialize(s, portfolio_size=portfolio_size)
