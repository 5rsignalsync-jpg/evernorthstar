"""Portfolio analysis — cross-reference user holdings against signals
and smart-money disclosures.

This is what makes the Pro brokerage-sync feature actually valuable: not
just 'here are your holdings' (your broker shows you that) but 'here's how
your holdings stack up against momentum signals and what smart money is doing
with the same tickers'.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, select

from crypto_trends.auth import db as auth_db
from crypto_trends.data.store import connect
from crypto_trends.portfolio.models import BrokerageAccount, Holding

log = logging.getLogger(__name__)


@dataclass
class AnnotatedHolding:
    """A user's position enriched with EverNorthstar signal data."""
    ticker: Optional[str]
    name: str
    security_type: Optional[str]
    quantity: float
    value: Optional[float]
    cost_basis: Optional[float]
    institution_name: str

    # Annotations
    momentum_score: Optional[float] = None   # -1 to +1 from signal_scores
    asset_class: Optional[str] = None
    smart_money_actors: list[str] = field(default_factory=list)  # top 3 actors holding this
    smart_money_buys_usd: float = 0.0
    smart_money_sells_usd: float = 0.0


@dataclass
class PortfolioSummary:
    """Top-line numbers shown above the holdings table."""
    total_value_usd: float
    n_holdings: int
    n_with_signal: int           # how many holdings we have a momentum signal for
    n_with_smart_money: int      # how many have ANY smart-money disclosure
    weighted_momentum_score: Optional[float]   # value-weighted across priced positions
    smart_money_overlap_pct: float             # % of value in tickers with 13F coverage
    momentum_quality_label: str                # 'strong' | 'mixed' | 'weak' | 'unscored'


def analyze_user_portfolio(user_id: int) -> tuple[PortfolioSummary, list[AnnotatedHolding]]:
    """Build the full annotated portfolio view for one user.

    Single DuckDB connection covers both annotations (signal_scores + smart_money_trades).
    SQLite reads are separate (small data, fast).
    """
    with Session(auth_db._engine) as session:
        rows = session.exec(
            select(Holding, BrokerageAccount)
            .join(BrokerageAccount, Holding.account_id == BrokerageAccount.id)
            .where(Holding.user_id == user_id)
        ).all()

    if not rows:
        return PortfolioSummary(
            total_value_usd=0.0, n_holdings=0, n_with_signal=0, n_with_smart_money=0,
            weighted_momentum_score=None, smart_money_overlap_pct=0.0,
            momentum_quality_label="unscored",
        ), []

    tickers = {h.ticker for h, _ in rows if h.ticker}

    # Fetch latest momentum scores + asset classes for these tickers
    scores: dict[str, tuple[float, str]] = {}  # ticker -> (score, asset_class)
    smart_money: dict[str, list[tuple[str, str, float]]] = {}  # ticker -> [(actor, side, amt)]

    if tickers:
        placeholders = ",".join("?" for _ in tickers)
        ticker_list = list(tickers)
        with connect(read_only=True) as conn:
            try:
                rows_q = conn.execute(
                    f"""
                    WITH latest AS (
                        SELECT s.symbol, max(s.ts) AS ts
                        FROM signal_scores s
                        WHERE s.signal_name = 'momentum_v1' AND s.symbol IN ({placeholders})
                        GROUP BY s.symbol
                    )
                    SELECT s.symbol, s.score, u.asset_class
                    FROM signal_scores s
                    JOIN latest l ON l.symbol = s.symbol AND l.ts = s.ts
                    JOIN universe u ON u.symbol = s.symbol
                    WHERE s.signal_name = 'momentum_v1'
                    """,
                    ticker_list,
                ).fetchall()
                for symbol, score, ac in rows_q:
                    scores[symbol] = (float(score), ac)
            except Exception as e:
                log.warning("portfolio: score lookup failed: %s", e)

            try:
                sm_rows = conn.execute(
                    f"""
                    SELECT ticker, actor_name, side, amount_min, disclosure_date
                    FROM smart_money_trades
                    WHERE ticker IN ({placeholders})
                      AND disclosure_date >= now() - INTERVAL '180 days'
                    ORDER BY disclosure_date DESC, amount_min DESC NULLS LAST
                    """,
                    ticker_list,
                ).fetchall()
                for ticker, actor, side, amount, _date in sm_rows:
                    smart_money.setdefault(ticker, []).append((actor, side, float(amount or 0)))
            except Exception as e:
                log.warning("portfolio: smart-money lookup failed: %s", e)

    # Annotate each holding + compute aggregates
    annotated: list[AnnotatedHolding] = []
    total_value = 0.0
    weighted_score_num = 0.0
    weighted_score_denom = 0.0
    n_with_signal = 0
    n_with_smart_money = 0
    smart_money_value = 0.0

    for h, account in rows:
        val = h.value or 0.0
        total_value += val
        score_info = scores.get(h.ticker) if h.ticker else None
        sm_info = smart_money.get(h.ticker, []) if h.ticker else []

        if score_info:
            n_with_signal += 1
            if val > 0:
                weighted_score_num += score_info[0] * val
                weighted_score_denom += val
        if sm_info:
            n_with_smart_money += 1
            smart_money_value += val

        # Top 3 actors by recency × size already (ORDER BY in SQL)
        top_actors = [a[0] for a in sm_info[:3]]
        buys = sum(a[2] for a in sm_info if a[1].lower() == "buy")
        sells = sum(a[2] for a in sm_info if a[1].lower() == "sell")

        annotated.append(AnnotatedHolding(
            ticker=h.ticker,
            name=h.name,
            security_type=h.security_type,
            quantity=h.quantity,
            value=h.value,
            cost_basis=h.cost_basis,
            institution_name=account.institution_name,
            momentum_score=score_info[0] if score_info else None,
            asset_class=score_info[1] if score_info else None,
            smart_money_actors=top_actors,
            smart_money_buys_usd=buys,
            smart_money_sells_usd=sells,
        ))

    # Sort by value desc — most important positions on top
    annotated.sort(key=lambda a: a.value or 0, reverse=True)

    weighted_score = weighted_score_num / weighted_score_denom if weighted_score_denom > 0 else None
    overlap_pct = (smart_money_value / total_value * 100.0) if total_value > 0 else 0.0

    if weighted_score is None:
        label = "unscored"
    elif weighted_score >= 0.3:
        label = "strong"
    elif weighted_score <= -0.3:
        label = "weak"
    else:
        label = "mixed"

    summary = PortfolioSummary(
        total_value_usd=total_value,
        n_holdings=len(annotated),
        n_with_signal=n_with_signal,
        n_with_smart_money=n_with_smart_money,
        weighted_momentum_score=weighted_score,
        smart_money_overlap_pct=overlap_pct,
        momentum_quality_label=label,
    )
    return summary, annotated
