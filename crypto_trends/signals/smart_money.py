"""smart_money_v1 — composite signal from 13F + insider + (future) Congress flows.

For each ticker in the equity universe, we aggregate three independent signals
of "smart money is buying":
  - **Institutional breadth** (13F): how many tracked funds hold it, and total $.
  - **Insider net flow** (Form 4): dollar value of recent insider buys minus
    sells (excluding programmed 10b5-1 sales).
  - **Congress net flow** (when ingester is wired): same pattern for Congress.

Each leg is normalized to roughly [-1, 1] via cross-sectional ranking, then
blended with default weights. Returns a per-ticker NamedTuple so the API can
surface both the score and the components.

Honest caveats (which the dashboard surfaces):
  - 13F is long-only equity book, 45-day lag, no shorts/derivatives.
  - Form 4 includes purchases AND sales; sales are noisy because most are 10b5-1.
  - Congress lag is 45 days legal max, often more.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from crypto_trends.data.store import connect

log = logging.getLogger(__name__)

SIGNAL_NAME = "smart_money_v1"


@dataclass(frozen=True)
class SmartMoneySignal:
    ticker: str
    score: float                # composite, roughly [-1, 1]
    n_funds_holding: int
    total_13f_value_usd: float
    insider_buys_usd: float
    insider_sells_usd: float
    insider_net_usd: float
    congress_buys_usd: float
    congress_sells_usd: float
    top_actors: list[dict]      # [{actor_name, source, side, amount}]


def _percentile_rank(s: pd.Series) -> pd.Series:
    """Map values to [0, 1] via rank/N. Constant input → 0.5."""
    if len(s) <= 1:
        return pd.Series(0.5, index=s.index)
    return s.rank(method="average", pct=True)


def _z(s: pd.Series) -> pd.Series:
    mu, sd = s.mean(), s.std()
    if sd == 0 or pd.isna(sd):
        return pd.Series(0.0, index=s.index)
    return (s - mu) / sd


def compute(window_days: int = 90) -> dict[str, SmartMoneySignal]:
    """Compute smart_money_v1 across every ticker in our equity universe.

    `window_days` bounds how far back insider/Congress flows are aggregated.
    13F holdings are point-in-time (latest filing), not flow-based, so the
    window only affects insider/Congress legs.
    """
    cutoff_iso = (datetime.utcnow() - timedelta(days=window_days)).date().isoformat()

    with connect(read_only=True) as conn:
        symbols = [r[0] for r in conn.execute(
            "SELECT symbol FROM universe WHERE asset_class IN "
            "('equity_large', 'equity_micro') AND included"
        ).fetchall()]

        if not symbols:
            return {}

        df_13f = conn.execute(
            """
            SELECT ticker, COUNT(DISTINCT actor_id) AS n_funds,
                   COALESCE(SUM(amount_min), 0) AS total_value
            FROM smart_money_trades
            WHERE source = '13f'
            GROUP BY ticker
            """
        ).fetchdf().set_index("ticker") if symbols else pd.DataFrame()

        df_insider = conn.execute(
            """
            SELECT ticker, side,
                   COALESCE(SUM(amount_min), 0) AS total
            FROM smart_money_trades
            WHERE source = 'insider'
              AND disclosure_date >= ?
              AND (notes IS NULL OR notes NOT LIKE '%10b5-1%')
            GROUP BY ticker, side
            """, [cutoff_iso],
        ).fetchdf()

        df_congress = conn.execute(
            """
            SELECT ticker, side, COALESCE(SUM((amount_min + amount_max) / 2), 0) AS total
            FROM smart_money_trades
            WHERE source IN ('congress_house', 'congress_senate')
              AND disclosure_date >= ?
            GROUP BY ticker, side
            """, [cutoff_iso],
        ).fetchdf()

        # Top actors per ticker — for the dashboard's "who" view.
        top_rows = conn.execute(
            """
            SELECT t.ticker, t.source, t.actor_name, t.side, t.amount_min, t.disclosure_date
            FROM smart_money_trades t
            WHERE t.disclosure_date >= ?
              AND t.amount_min IS NOT NULL
              AND t.amount_min > 0
            ORDER BY t.amount_min DESC
            """, [cutoff_iso],
        ).fetchall()

    # Build per-ticker frame.
    base = pd.DataFrame(index=symbols)
    base["n_funds"] = df_13f["n_funds"].reindex(symbols).fillna(0).astype(int) \
        if not df_13f.empty else 0
    base["total_13f_value"] = df_13f["total_value"].reindex(symbols).fillna(0) \
        if not df_13f.empty else 0.0

    if not df_insider.empty:
        pivoted = df_insider.pivot_table(
            index="ticker", columns="side", values="total", aggfunc="sum"
        ).fillna(0)
        base["insider_buys"] = pivoted.get("buy", pd.Series(0, index=symbols)).reindex(symbols).fillna(0)
        base["insider_sells"] = pivoted.get("sell", pd.Series(0, index=symbols)).reindex(symbols).fillna(0)
    else:
        base["insider_buys"] = 0.0
        base["insider_sells"] = 0.0
    base["insider_net"] = base["insider_buys"] - base["insider_sells"]

    if not df_congress.empty:
        pivoted = df_congress.pivot_table(
            index="ticker", columns="side", values="total", aggfunc="sum"
        ).fillna(0)
        base["congress_buys"] = pivoted.get("buy", pd.Series(0, index=symbols)).reindex(symbols).fillna(0)
        base["congress_sells"] = pivoted.get("sell", pd.Series(0, index=symbols)).reindex(symbols).fillna(0)
    else:
        base["congress_buys"] = 0.0
        base["congress_sells"] = 0.0

    # Compose score. Weights default to 0.45 / 0.45 / 0.10 across the 3 legs.
    # If a leg has no data at all, redistribute its weight equally.
    weights = {"13f": 0.45, "insider": 0.45, "congress": 0.10}
    if base["insider_net"].abs().sum() == 0:
        weights = {"13f": 0.85, "insider": 0.0, "congress": 0.15}
    if (base["congress_buys"].sum() + base["congress_sells"].sum()) == 0:
        weights["congress"] = 0.0
    total_w = sum(weights.values()) or 1.0

    # 13F leg: high n_funds + high total value → high score.
    breadth_pct = _percentile_rank(base["n_funds"].astype(float))
    value_pct = _percentile_rank(base["total_13f_value"])
    score_13f = (breadth_pct + value_pct) / 2 * 2 - 1   # rescale [0,1] → [-1,1]
    score_insider = _z(base["insider_net"]).clip(-3, 3) / 3
    score_congress = _z(base["congress_buys"] - base["congress_sells"]).clip(-3, 3) / 3

    composite = (
        weights["13f"] * score_13f
        + weights["insider"] * score_insider
        + weights["congress"] * score_congress
    ) / total_w

    # Build top_actors per ticker (preview of the drill-down view).
    top_actors_by_ticker: dict[str, list[dict]] = {}
    for ticker, source, actor_name, side, amount, disc in top_rows:
        lst = top_actors_by_ticker.setdefault(ticker, [])
        if len(lst) >= 5:
            continue
        lst.append({
            "actor_name": actor_name, "source": source,
            "side": side, "amount": float(amount) if amount is not None else None,
            "disclosure_date": str(disc) if disc else None,
        })

    return {
        t: SmartMoneySignal(
            ticker=t,
            score=float(composite.get(t, 0.0)),
            n_funds_holding=int(base.at[t, "n_funds"]),
            total_13f_value_usd=float(base.at[t, "total_13f_value"]),
            insider_buys_usd=float(base.at[t, "insider_buys"]),
            insider_sells_usd=float(base.at[t, "insider_sells"]),
            insider_net_usd=float(base.at[t, "insider_net"]),
            congress_buys_usd=float(base.at[t, "congress_buys"]),
            congress_sells_usd=float(base.at[t, "congress_sells"]),
            top_actors=top_actors_by_ticker.get(t, []),
        )
        for t in symbols
    }


def actor_basket(actor_id: str, limit: int = 20) -> list[dict]:
    """Return the top positions for an individual actor — the 'follow X' view."""
    with connect(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT ticker, source, side, MAX(disclosure_date) AS last_disclosed,
                   SUM(COALESCE(amount_min, 0)) AS total_min,
                   SUM(COALESCE(amount_max, 0)) AS total_max,
                   SUM(COALESCE(shares, 0)) AS total_shares
            FROM smart_money_trades
            WHERE actor_id = ?
            GROUP BY ticker, source, side
            ORDER BY total_min DESC NULLS LAST
            LIMIT ?
            """, [actor_id, limit],
        ).fetchall()

    return [
        {
            "ticker": ticker, "source": source, "side": side,
            "last_disclosed": str(last) if last else None,
            "amount_min": float(amin) if amin else None,
            "amount_max": float(amax) if amax else None,
            "shares": float(shares) if shares else None,
        }
        for ticker, source, side, last, amin, amax, shares in rows
    ]


def list_actors() -> list[dict]:
    """Return all tracked actors with their trade counts."""
    with connect(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT actor_id, actor_name, actor_role, source,
                   COUNT(*) AS n_trades,
                   MAX(disclosure_date) AS last_disclosed
            FROM smart_money_trades
            GROUP BY actor_id, actor_name, actor_role, source
            ORDER BY n_trades DESC
            """
        ).fetchall()
    return [
        {"actor_id": a_id, "actor_name": name, "actor_role": role,
         "source": source, "n_trades": int(n),
         "last_disclosed": str(last) if last else None}
        for a_id, name, role, source, n, last in rows
    ]
