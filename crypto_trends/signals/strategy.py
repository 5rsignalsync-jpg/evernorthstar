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
class Performance:
    """'If you'd bought this strategy's basket on the most recent disclosure
    date and held until today, here's how you'd have done.' Honest because
    we use prices from when the filing FIRST BECAME PUBLIC, not when the
    investor actually bought (which is 45 days earlier under 13F lag).

    MVP shows just the weighted-return; we'll add an S&P benchmark in a
    follow-up after we add SPY to the universe.
    """
    since: str              # ISO date of last disclosure
    days_held: int
    strategy_return_pct: float           # weighted avg return of basket
    tickers_priced: int                  # positions we could price
    tickers_unpriced: int                # positions we couldn't price (skipped)


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
    performance: Performance | None = None


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


def _compute_performance(
    positions: list[Position], last_activity_str: str | None,
) -> Performance | None:
    """Compute 'live return since last disclosure' for a strategy's basket.

    Returns None if we can't price enough positions or if the disclosure is
    too recent. Honest fallback — we'd rather show nothing than show a number
    we can't back up.
    """
    if not positions or not last_activity_str:
        return None
    try:
        since = pd.Timestamp(last_activity_str)
    except Exception:
        return None

    bases = [p.ticker for p in positions]
    weights = {p.ticker: abs(p.weight) for p in positions}

    with connect(read_only=True) as conn:
        row = conn.execute(
            "SELECT MAX(ts) FROM ohlcv "
            "WHERE asset_class IN ('equity_large','equity_micro')",
        ).fetchone()
        if not row or row[0] is None:
            return None
        latest_ts = pd.Timestamp(row[0])
        if latest_ts <= since or (latest_ts - since).days < 7:
            # Too recent to be meaningful (less than a week of trading)
            return None

        placeholders = ",".join(["?"] * len(bases))
        # Fetch the close PRICE at "since" (or closest weekday) and at latest_ts
        # for each unique base ticker via a CTE.
        # ABS(EXTRACT(epoch FROM (ts - since))) finds the nearest bar.
        try:
            df = conn.execute(
                f"""
                WITH starts AS (
                    SELECT u.base, o.close,
                           row_number() OVER (
                               PARTITION BY u.base
                               ORDER BY ABS(EPOCH(o.ts - ?::TIMESTAMP))
                           ) AS rn
                    FROM ohlcv o JOIN universe u ON u.symbol = o.symbol
                    WHERE u.base IN ({placeholders})
                      AND o.asset_class IN ('equity_large','equity_micro')
                      AND o.ts BETWEEN (?::TIMESTAMP - INTERVAL '14 days')
                                   AND (?::TIMESTAMP + INTERVAL '14 days')
                ),
                ends AS (
                    SELECT u.base, o.close,
                           row_number() OVER (
                               PARTITION BY u.base
                               ORDER BY o.ts DESC
                           ) AS rn
                    FROM ohlcv o JOIN universe u ON u.symbol = o.symbol
                    WHERE u.base IN ({placeholders})
                      AND o.asset_class IN ('equity_large','equity_micro')
                )
                SELECT s.base, s.close AS start_close, e.close AS end_close
                FROM starts s JOIN ends e ON e.base = s.base
                WHERE s.rn = 1 AND e.rn = 1
                """,
                [since, *bases, since, since, *bases],
            ).fetchdf()
        except Exception:
            return None

    if df.empty:
        return Performance(
            since=str(since.date()),
            days_held=(latest_ts - since).days,
            strategy_return_pct=0.0,
            tickers_priced=0,
            tickers_unpriced=len(positions),
        )

    df["ret"] = (df["end_close"] / df["start_close"] - 1.0) * 100.0
    df["weight"] = df["base"].map(weights).astype(float)
    # Renormalize weights among the positions we can actually price.
    w_sum = df["weight"].sum()
    if w_sum <= 0:
        return None
    df["weight"] = df["weight"] / w_sum

    strategy_return = float((df["ret"] * df["weight"]).sum())

    return Performance(
        since=str(since.date()),
        days_held=(latest_ts - since).days,
        strategy_return_pct=round(strategy_return, 2),
        tickers_priced=int(len(df)),
        tickers_unpriced=int(len(positions) - len(df)),
    )


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

    perf = _compute_performance(positions, last_activity) if ready else None

    card = StrategyCard(
        slug=s.slug, name=s.name, emoji=s.emoji,
        description=s.description, caveats=list(s.caveats),
        ready=ready,
        gated_reason=gated_reason,
        n_positions=n_positions,
        last_activity=last_activity,
        performance=perf,
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
