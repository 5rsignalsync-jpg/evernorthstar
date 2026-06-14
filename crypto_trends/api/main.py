"""FastAPI app serving signal rankings to the dashboard.

Endpoints:
    GET /health            health probe
    GET /rankings          latest top-N long / bottom-N short with metadata
    GET /history/{symbol}  recent OHLCV + score history for one symbol

CORS is open to localhost:3000 for the Next.js dev server. Lock down before
deploying.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from crypto_trends.auth.db import init_users_db
from crypto_trends.auth.deps import current_user, require_pro
from crypto_trends.auth.models import User
from crypto_trends.alerts.routes import router as alerts_router
from crypto_trends.auth.routes import router as auth_router
from crypto_trends.auth.tiers import limits_for
from crypto_trends.payments.nowpayments_routes import router as nowpayments_router
from crypto_trends.payments.stripe_routes import router as stripe_router
from crypto_trends.portfolio.routes import router as portfolio_router
from crypto_trends.config import settings
from crypto_trends.data.ingest.earnings import upcoming_by_symbol
from crypto_trends.data.store import connect
from crypto_trends.signals import smart_money, strategy as strategy_sig
from crypto_trends.signals.news import compute_for_asset_class as compute_news

def _rate_key(request: Request) -> str:
    """Rate-limit by session cookie when present, else by IP. Authenticated
    users get a higher quota tied to their session, anonymous users share an
    IP bucket so a noisy LAN doesn't exhaust everyone's quota."""
    cookie = request.cookies.get(settings.auth_cookie_name)
    if cookie:
        # First 16 chars of the JWT are stable per session — enough for keying.
        return f"sess:{cookie[:16]}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_key, default_limits=["60/minute"])

app = FastAPI(title="EverNorthstar", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS must allow credentials + POST for cookie-based auth flow.
# Origins come from settings.cors_origins (comma-separated env var) so prod
# deploys can add their Vercel URL without code changes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    from crypto_trends.startup_checks import assert_production_ready
    assert_production_ready()
    init_users_db()


app.include_router(auth_router)
app.include_router(stripe_router)
app.include_router(nowpayments_router)
app.include_router(alerts_router)
app.include_router(portfolio_router)


class RankingRow(BaseModel):
    symbol: str
    base: str
    score: float
    rank: int            # universe rank (1 = largest)
    price: float | None
    pct_change_24h: float | None
    components: dict | None
    # News overlay (computed inline; cheap for our universe sizes).
    headline: str | None = None
    headline_publisher: str | None = None
    headline_at: datetime | None = None
    news_buzz: int | None = None
    news_sentiment: float | None = None
    negative_event: bool = False
    # Next upcoming earnings date (ISO string) if within ~30 days.
    upcoming_earnings: str | None = None
    days_to_earnings: int | None = None


class RankingsResponse(BaseModel):
    signal_name: str
    asset_class: str
    long_only: bool
    computed_at: datetime
    longs: list[RankingRow]
    shorts: list[RankingRow]
    # Tier metadata so the UI can render upsells without trusting the client.
    tier: str = "free"            # "free" | "pro"
    requested_top_n: int = 5      # what the client asked for
    delivered_top_n: int = 5      # what we actually returned (clamped to tier)
    upsell_text: str | None = None
    disclaimer: str = (
        "Not financial advice. Outputs are research signals only. "
        "Trading carries substantial risk including total loss of principal."
    )


class HistoryPoint(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    score: float | None = None


class HistoryHeadline(BaseModel):
    ts: datetime
    headline: str
    publisher: str | None
    url: str | None
    sentiment: float | None


class SymbolDetail(BaseModel):
    symbol: str
    base: str
    asset_class: str
    interval: str
    price_series: list[HistoryPoint]
    headlines: list[HistoryHeadline]
    disclaimer: str = (
        "Not financial advice. Outputs are research signals only. "
        "Trading carries substantial risk including total loss of principal."
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class AssetClassFreshness(BaseModel):
    asset_class: str
    latest_bar: datetime | None
    age_seconds: int | None
    age_human: str             # "5m", "3h", "2d" — for the UI

    @property
    def severity(self) -> str:
        """green / amber / red — bucket based on tier-typical refresh cadence.

        Crypto trades 24/7, so > 24h stale is genuinely bad.
        Equities trade Mon–Fri, so "the last trading day's close" can be 3+ days
        old over a long weekend (e.g., Memorial Day) and still be the freshest
        data that exists. We use a longer threshold for equity sleeves.
        """
        if self.age_seconds is None:
            return "red"
        age = max(0, self.age_seconds)  # clamp clock skew

        is_equity = self.asset_class.startswith("equity")
        green_max = 24 * 3600 if is_equity else 4 * 3600
        amber_max = 5 * 86400 if is_equity else 24 * 3600

        if age < green_max:
            return "green"
        if age < amber_max:
            return "amber"
        return "red"


class FreshnessResponse(BaseModel):
    asset_classes: list[AssetClassFreshness]
    worst_severity: str    # green / amber / red — for the header dot color


def _human_age(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    # Negative ages happen when DuckDB's `now()` clock lags slightly behind the
    # latest bar's timestamp (e.g., during a fresh ingest). Treat as "fresh".
    if seconds <= 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


class MarketMoodResponse(BaseModel):
    """Crypto Fear & Greed Index from alternative.me. 0=Extreme Fear, 100=Extreme Greed."""
    value: int
    classification: str  # "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed"
    fetched_at: datetime
    source: str = "alternative.me"
    asset_class: str = "crypto"


# Module-level cache: alternative.me publishes once per day, so 1-hour caching is
# generous + protects us if their API goes down briefly. Memory cache is fine —
# even if Fly auto-stops the machine, the cache reloads on next request.
_market_mood_cache: dict = {"data": None, "ts": 0.0}


@app.get("/status/market_mood", response_model=MarketMoodResponse)
def status_market_mood() -> MarketMoodResponse:
    """Crypto Fear & Greed Index — cached 1h to avoid hammering alternative.me."""
    import time as _t

    import httpx

    now = _t.time()
    cached = _market_mood_cache["data"]
    if cached is not None and now - _market_mood_cache["ts"] < 3600:
        return cached  # type: ignore[return-value]

    try:
        r = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=8.0)
        r.raise_for_status()
        item = r.json()["data"][0]
        result = MarketMoodResponse(
            value=int(item["value"]),
            classification=item["value_classification"],
            fetched_at=datetime.utcfromtimestamp(int(item["timestamp"])),
        )
        _market_mood_cache["data"] = result
        _market_mood_cache["ts"] = now
        return result
    except Exception as e:
        # Serve stale cache if we have one — better than erroring.
        if cached is not None:
            return cached  # type: ignore[return-value]
        raise HTTPException(503, f"Market mood unavailable: {e}") from e


@app.get("/status/freshness", response_model=FreshnessResponse)
def status_freshness() -> FreshnessResponse:
    """Per-asset-class data staleness so the UI can flag stale prices."""
    with connect(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT asset_class,
                   MAX(ts) AS latest_bar,
                   CAST(EXTRACT(epoch FROM (now()::TIMESTAMP - MAX(ts))) AS BIGINT)
                       AS age_seconds
            FROM ohlcv
            GROUP BY asset_class
            ORDER BY asset_class
            """
        ).fetchall()

    items: list[AssetClassFreshness] = []
    for asset_class, latest_bar, age_seconds in rows:
        age = int(age_seconds) if age_seconds is not None else None
        items.append(AssetClassFreshness(
            asset_class=asset_class,
            latest_bar=latest_bar,
            age_seconds=age,
            age_human=_human_age(age),
        ))

    # Worst severity sets the header indicator color.
    SEVERITIES = ("green", "amber", "red")
    worst = "green"
    for it in items:
        if SEVERITIES.index(it.severity) > SEVERITIES.index(worst):
            worst = it.severity

    return FreshnessResponse(asset_classes=items, worst_severity=worst)


def _rankings_data(
    asset_class: str,
    signal_name: str,
    top_n: int,
    user: User | None,
) -> RankingsResponse:
    """Pure data layer for /rankings — also called by /rankings.csv internally
    with a known user. Keeps the gating logic in one place."""
    long_only = signal_name == "long_term_v1"
    tier = limits_for(user)
    requested_top_n = top_n
    effective_top_n = min(top_n, tier.top_n)

    with connect(read_only=True) as conn:
        latest = conn.execute(
            """
            SELECT MAX(s.ts)
            FROM signal_scores s
            JOIN universe u ON u.symbol = s.symbol
            WHERE s.signal_name = ? AND u.asset_class = ?
            """,
            [signal_name, asset_class],
        ).fetchone()
        if not latest or latest[0] is None:
            raise HTTPException(
                503,
                f"No {signal_name} signals for {asset_class}. Run signal runner.",
            )
        latest_ts = latest[0]

        rows = conn.execute(
            """
            SELECT s.symbol, u.base, s.score, u."rank", s.components,
                   latest.close, prev.close AS close_24h_ago
            FROM signal_scores s
            JOIN universe u ON u.symbol = s.symbol
            LEFT JOIN ohlcv latest
              ON latest.symbol = s.symbol
             AND latest.ts = (SELECT MAX(ts) FROM ohlcv WHERE symbol = s.symbol)
            LEFT JOIN ohlcv prev
              ON prev.symbol = s.symbol
             AND prev.ts = (
                SELECT MAX(ts) FROM ohlcv
                WHERE symbol = s.symbol
                  AND ts <= (SELECT MAX(ts) - INTERVAL 1 DAY FROM ohlcv WHERE symbol = s.symbol)
             )
            WHERE s.signal_name = ?
              AND s.ts = ?
              AND u.asset_class = ?
              AND u.included
            """,
            [signal_name, latest_ts, asset_class],
        ).fetchall()

    # Compute news overlay once per request (one query + small in-memory aggregation).
    news_by_sym = compute_news(asset_class)
    earnings_by_sym = upcoming_by_symbol(within_days=30) \
        if asset_class.startswith("equity") else {}

    def row_to_model(r) -> RankingRow:
        sym, base, score, rank, components_json, price, prev_close = r
        pct = None
        if price is not None and prev_close not in (None, 0):
            pct = (price - prev_close) / prev_close * 100.0

        # Look up news with fallback to a separate publisher field; the symbol
        # in news matches the universe symbol exactly.
        n = news_by_sym.get(sym)

        # Fetch headline publisher from the latest news row (cheap, lazy).
        publisher = None
        if n and n.recent_headline:
            with connect(read_only=True) as conn2:
                pr = conn2.execute(
                    "SELECT publisher FROM news WHERE symbol = ? AND headline = ? "
                    "ORDER BY published_at DESC LIMIT 1",
                    [sym, n.recent_headline],
                ).fetchone()
                publisher = pr[0] if pr else None

        e_date = earnings_by_sym.get(sym)
        days_to = None
        if e_date:
            try:
                days_to = (datetime.fromisoformat(e_date).date()
                           - datetime.utcnow().date()).days
            except ValueError:
                days_to = None

        return RankingRow(
            symbol=sym, base=base, score=float(score), rank=int(rank) if rank else 9999,
            price=float(price) if price is not None else None,
            pct_change_24h=pct,
            components=json.loads(components_json) if components_json else None,
            headline=(n.recent_headline if n else None),
            headline_publisher=publisher,
            headline_at=(n.recent_headline_at if n else None),
            news_buzz=(n.buzz if n else None),
            news_sentiment=(n.sentiment_avg if n else None),
            negative_event=(n.negative_event if n else False),
            upcoming_earnings=e_date,
            days_to_earnings=days_to,
        )

    models = [row_to_model(r) for r in rows]
    models.sort(key=lambda m: m.score, reverse=True)

    # Each side is capped at floor(universe / 2) so longs and shorts are always
    # disjoint sets — same ticker can't be both a relative outperformer AND
    # a relative underperformer. With the Crypto sleeve only having ~26 names
    # and Pro asking for top_n=25, naïve top-N + bottom-N would overlap on
    # ~24 tickers. The cap ensures the worst case is the bottom-of-longs ≠
    # top-of-shorts (one ticker each side, no shared symbols).
    half_cap = len(models) // 2
    per_side = min(effective_top_n, half_cap) if not long_only else effective_top_n

    longs = models[:per_side]
    shorts = [] if long_only else list(reversed(models[-per_side:])) if per_side > 0 else []

    upsell = None
    if effective_top_n < requested_top_n:
        upsell = (
            f"Free tier shows top {effective_top_n}. "
            f"Upgrade to Pro for the full top {requested_top_n} ranking."
        )

    return RankingsResponse(
        signal_name=signal_name,
        asset_class=asset_class,
        long_only=long_only,
        computed_at=latest_ts,
        longs=longs,
        shorts=shorts,
        tier=tier.tier_name,
        requested_top_n=requested_top_n,
        delivered_top_n=effective_top_n,
        upsell_text=upsell,
    )


@app.get("/rankings", response_model=RankingsResponse)
@limiter.limit("30/minute")
def rankings(
    request: Request,
    asset_class: str = Query("crypto"),
    signal_name: str = Query("momentum_v1"),
    top_n: int = Query(5, ge=1, le=25),
    user: User | None = Depends(current_user),
) -> RankingsResponse:
    return _rankings_data(asset_class, signal_name, top_n, user)


@app.get("/rankings.csv")
def rankings_csv(
    asset_class: str = Query("crypto"),
    signal_name: str = Query("momentum_v1"),
    top_n: int = Query(25, ge=1, le=100),
    user: User = Depends(require_pro),    # CSV export is Pro-only
) -> StreamingResponse:
    """Flat CSV of the rankings — long leg first, then shorts (with side column).

    Easier than the JSON endpoint for spreadsheet workflows.
    """
    data = _rankings_data(asset_class, signal_name, top_n, user)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "side", "rank", "symbol", "base", "score", "price", "pct_change_24h",
        "news_buzz", "news_sentiment", "negative_event", "headline_publisher",
        "headline_at", "headline", "signal_name", "asset_class", "computed_at",
    ])
    for side, rows in (("LONG", data.longs), ("SHORT", data.shorts)):
        for i, r in enumerate(rows, 1):
            writer.writerow([
                side, i, r.symbol, r.base, f"{r.score:.6f}",
                f"{r.price:.6f}" if r.price is not None else "",
                f"{r.pct_change_24h:.4f}" if r.pct_change_24h is not None else "",
                r.news_buzz if r.news_buzz is not None else "",
                f"{r.news_sentiment:.4f}" if r.news_sentiment is not None else "",
                "TRUE" if r.negative_event else "FALSE",
                r.headline_publisher or "",
                r.headline_at.isoformat() if r.headline_at else "",
                (r.headline or "").replace("\n", " "),
                data.signal_name, data.asset_class, data.computed_at.isoformat(),
            ])

    buf.seek(0)
    filename = f"rankings_{asset_class}_{signal_name}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class SmartMoneyLeader(BaseModel):
    ticker: str
    score: float
    n_funds_holding: int
    total_13f_value_usd: float
    insider_buys_usd: float
    insider_sells_usd: float
    insider_net_usd: float
    congress_buys_usd: float
    congress_sells_usd: float
    top_actors: list[dict]


class SmartMoneyResponse(BaseModel):
    window_days: int
    top_n: int
    leaders: list[SmartMoneyLeader]
    tier: str = "free"
    requested_top_n: int = 25
    delivered_top_n: int = 25
    upsell_text: str | None = None
    disclaimer: str = (
        "13F filings: 45-day lag, long-only US equity book — no shorts, "
        "derivatives, or foreign positions. Form 4 insider trades: 2-day lag "
        "but many sales are programmed (10b5-1). Congress: 45-day legal max lag."
    )


class ActorSummary(BaseModel):
    actor_id: str
    actor_name: str
    actor_role: str | None
    source: str
    n_trades: int
    last_disclosed: str | None


class PerformanceModel(BaseModel):
    since: str
    days_held: int
    strategy_return_pct: float
    tickers_priced: int
    tickers_unpriced: int


class StrategyCardModel(BaseModel):
    slug: str
    name: str
    emoji: str
    description: str
    caveats: list[str]
    ready: bool
    gated_reason: str | None
    n_positions: int
    last_activity: str | None
    performance: PerformanceModel | None = None


class PositionModel(BaseModel):
    ticker: str
    weight: float
    value_usd: float
    suggested_usd: float
    note: str | None = None


class ActivityModel(BaseModel):
    ticker: str
    actor_name: str
    side: str
    amount_usd: float | None
    disclosure_date: str
    source: str
    note: str | None = None


class StrategyDetailModel(BaseModel):
    card: StrategyCardModel
    inverse: bool
    portfolio_size: float
    positions: list[PositionModel]
    recent_activity: list[ActivityModel]
    disclaimer: str = (
        "Strategies mirror publicly-disclosed positions with a 2–45 day lag. "
        "Backtested performance is unavailable here; treat as research, not advice."
    )


def _card_to_model(c: "strategy_sig.StrategyCard") -> StrategyCardModel:
    """Convert internal dataclass to Pydantic model, including the nested
    Performance which __dict__ spread can't auto-convert."""
    perf_model = (
        PerformanceModel(**c.performance.__dict__) if c.performance else None
    )
    return StrategyCardModel(
        slug=c.slug, name=c.name, emoji=c.emoji,
        description=c.description, caveats=list(c.caveats),
        ready=c.ready, gated_reason=c.gated_reason,
        n_positions=c.n_positions, last_activity=c.last_activity,
        performance=perf_model,
    )


@app.get("/strategies", response_model=list[StrategyCardModel])
def strategies_list() -> list[StrategyCardModel]:
    return [_card_to_model(c) for c in strategy_sig.list_cards()]


@app.get("/strategies/{slug}", response_model=StrategyDetailModel)
def strategy_detail(
    slug: str,
    portfolio_size: float = Query(10_000.0, ge=100.0, le=10_000_000.0),
    user: User | None = Depends(current_user),
) -> StrategyDetailModel:
    det = strategy_sig.detail(slug, portfolio_size=portfolio_size)
    if det is None:
        raise HTTPException(404, f"Unknown strategy: {slug}")
    tier = limits_for(user)
    positions = det.positions[: tier.strategy_positions]
    activity = det.recent_activity[: tier.strategy_positions]
    return StrategyDetailModel(
        card=_card_to_model(det.card),
        inverse=det.inverse,
        portfolio_size=det.portfolio_size,
        positions=[PositionModel(**p.__dict__) for p in positions],
        recent_activity=[ActivityModel(**a.__dict__) for a in activity],
    )


@app.get("/smart_money/leaders", response_model=SmartMoneyResponse)
@limiter.limit("30/minute")
def smart_money_leaders(
    request: Request,
    window_days: int = Query(90, ge=7, le=365),
    top_n: int = Query(25, ge=1, le=100),
    user: User | None = Depends(current_user),
) -> SmartMoneyResponse:
    tier = limits_for(user)
    requested_top_n = top_n
    effective_top_n = min(top_n, tier.top_n)

    sigs = smart_money.compute(window_days=window_days)
    if not sigs:
        return SmartMoneyResponse(
            window_days=window_days, top_n=top_n, leaders=[],
            tier=tier.tier_name,
            requested_top_n=requested_top_n,
            delivered_top_n=effective_top_n,
        )

    ranked = sorted(sigs.values(), key=lambda s: s.score, reverse=True)[:effective_top_n]
    upsell = None
    if effective_top_n < requested_top_n:
        upsell = (
            f"Free tier shows top {effective_top_n} of the Smart Money leaderboard. "
            f"Upgrade to Pro for the full top {requested_top_n} plus every actor's "
            f"basket (Burry, Buffett, Ackman, Pelosi, …)."
        )
    return SmartMoneyResponse(
        window_days=window_days, top_n=top_n,
        leaders=[
            SmartMoneyLeader(
                ticker=s.ticker, score=s.score,
                n_funds_holding=s.n_funds_holding,
                total_13f_value_usd=s.total_13f_value_usd,
                insider_buys_usd=s.insider_buys_usd,
                insider_sells_usd=s.insider_sells_usd,
                insider_net_usd=s.insider_net_usd,
                congress_buys_usd=s.congress_buys_usd,
                congress_sells_usd=s.congress_sells_usd,
                top_actors=s.top_actors,
            )
            for s in ranked
        ],
        tier=tier.tier_name,
        requested_top_n=requested_top_n,
        delivered_top_n=effective_top_n,
        upsell_text=upsell,
    )


@app.get("/smart_money/actors", response_model=list[ActorSummary])
def smart_money_actors() -> list[ActorSummary]:
    return [ActorSummary(**a) for a in smart_money.list_actors()]


@app.get("/smart_money/actors/{actor_id}")
def smart_money_actor_basket(actor_id: str, limit: int = Query(20, ge=1, le=100)):
    basket = smart_money.actor_basket(actor_id, limit=limit)
    if not basket:
        raise HTTPException(404, f"No positions found for actor {actor_id}")
    return {"actor_id": actor_id, "positions": basket}


@app.get("/history/{symbol}", response_model=SymbolDetail)
@limiter.limit("60/minute")
def history(
    request: Request,
    symbol: str,
    days: int = Query(90, ge=1, le=730),
    signal_name: str = Query("momentum_v1"),
    user: User | None = Depends(current_user),
) -> SymbolDetail:
    """Full detail panel: OHLC bars + signal score per bar + recent headlines."""
    tier = limits_for(user)
    days = min(days, tier.history_days)
    with connect(read_only=True) as conn:
        meta = conn.execute(
            "SELECT base, asset_class FROM universe WHERE symbol = ?",
            [symbol],
        ).fetchone()
        if not meta:
            raise HTTPException(404, f"Symbol not in universe: {symbol}")
        base, asset_class = meta

        # Interval depends on asset class — crypto is hourly, equities daily.
        interval = "1h" if asset_class == "crypto" else "1d"

        price_rows = conn.execute(
            """
            SELECT o.ts, o.open, o.high, o.low, o.close, o.volume, s.score
            FROM ohlcv o
            LEFT JOIN signal_scores s
              ON s.symbol = o.symbol AND s.ts = o.ts AND s.signal_name = ?
            WHERE o.symbol = ?
              AND o.interval = ?
              AND o.ts >= (SELECT MAX(ts) - INTERVAL (?) DAY
                           FROM ohlcv WHERE symbol = ?)
            ORDER BY o.ts
            """,
            [signal_name, symbol, interval, days, symbol],
        ).fetchall()

        if not price_rows:
            raise HTTPException(404, f"No price data for {symbol}")

        news_rows = conn.execute(
            f"""
            SELECT published_at, headline, publisher, url, sentiment
            FROM news
            WHERE symbol = ?
              AND published_at >= (SELECT MAX(published_at) - INTERVAL 7 DAY
                                   FROM news WHERE symbol = ?)
            ORDER BY published_at DESC
            LIMIT {tier.history_headlines}
            """,
            [symbol, symbol],
        ).fetchall()

    return SymbolDetail(
        symbol=symbol,
        base=base,
        asset_class=asset_class,
        interval=interval,
        price_series=[
            HistoryPoint(
                ts=ts, open=float(o), high=float(h), low=float(low_),
                close=float(c), volume=float(v) if v is not None else None,
                score=float(s) if s is not None else None,
            )
            for ts, o, h, low_, c, v, s in price_rows
        ],
        headlines=[
            HistoryHeadline(
                ts=ts, headline=h, publisher=p, url=u,
                sentiment=float(sent) if sent is not None else None,
            )
            for ts, h, p, u, sent in news_rows
        ],
    )


# ─── Ticker search + external (off-universe) lookup ──────────────────────
#
# Watchlist users want to track tickers we don't rank (e.g., MSTR, GME,
# specific crypto not on Binance.US). These endpoints let the frontend
# look up any ticker via yfinance and pull a live quote for display in the
# watchlist, even when the ticker isn't in our universe.

class TickerSearchResult(BaseModel):
    symbol: str
    base: str
    name: str | None = None
    asset_class: str  # one of our existing ACs, or "external" for yfinance lookups
    price: float | None = None
    pct_change_24h: float | None = None
    in_universe: bool
    description: str | None = None  # truncated to ~280 chars for search dropdown


class ExternalQuote(BaseModel):
    symbol: str
    name: str | None
    price: float | None
    pct_change_24h: float | None
    fetched_at: datetime
    description: str | None = None  # full business summary (no truncation)


class TickerDescription(BaseModel):
    """Lazy-loaded long-form description for drilldown context."""
    symbol: str
    name: str | None
    description: str | None
    fetched_at: datetime


# Memory cache: avoid hammering yfinance for repeated lookups within an hour.
_yf_cache: dict[str, tuple[float, dict]] = {}
_YF_CACHE_TTL_SEC = 3600


# CoinGecko fallback for tickers yfinance doesn't cover (most non-Binance.US
# alts: ZBCN, BONK on some exchanges, etc.). Free public API, no key needed.
# Free tier: ~30 req/min — well below what a single user could hit.
_cg_cache: dict[str, tuple[float, dict]] = {}
_CG_BASE = "https://api.coingecko.com/api/v3"


def _cg_lookup(ticker: str) -> dict | None:
    """Find a crypto on CoinGecko by ticker. Returns dict with name, price,
    pct_change_24h, description. Cached 1h."""
    import time as _t
    ticker = ticker.strip().upper()
    if not ticker:
        return None
    now = _t.time()
    if ticker in _cg_cache:
        ts, cached = _cg_cache[ticker]
        if now - ts < _YF_CACHE_TTL_SEC:
            return cached
    try:
        import httpx
        with httpx.Client(timeout=8.0) as client:
            # 1) Search for coin by ticker to get its CoinGecko id
            sr = client.get(f"{_CG_BASE}/search", params={"query": ticker})
            sr.raise_for_status()
            coins = sr.json().get("coins", [])
            if not coins:
                _cg_cache[ticker] = (now, {})
                return None
            # Prefer exact symbol match; CG search ranks them by market cap already
            exact = next((c for c in coins if c.get("symbol", "").upper() == ticker), None)
            best = exact or coins[0]
            coin_id = best.get("id")
            if not coin_id:
                return None
            # 2) Fetch full info — price + description in one call
            cr = client.get(
                f"{_CG_BASE}/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false",
                },
            )
            cr.raise_for_status()
            info = cr.json()
            market = info.get("market_data", {}) or {}
            price = market.get("current_price", {}).get("usd")
            pct = market.get("price_change_percentage_24h")
            description = (info.get("description", {}) or {}).get("en") or None
            if description:
                # Strip HTML tags + truncate for sanity
                import re
                description = re.sub(r"<[^>]+>", "", description).strip()
            result = {
                "name": info.get("name"),
                "price": float(price) if price is not None else None,
                "pct_change_24h": float(pct) if pct is not None else None,
                "description": description,
                "cg_id": coin_id,
            }
            _cg_cache[ticker] = (now, result)
            return result
    except Exception:
        return None


def _yf_lookup(ticker: str) -> dict | None:
    """Validate + fetch a yfinance ticker. Returns None if invalid or offline.

    Cached for 1h to avoid repeated 1-2s API calls for the same ticker.
    Returns dict with keys: name, price, pct_change_24h. None if not found.
    """
    import time as _t
    ticker = ticker.strip().upper()
    if not ticker or len(ticker) > 12:
        return None
    now = _t.time()
    if ticker in _yf_cache:
        ts, cached = _yf_cache[ticker]
        if now - ts < _YF_CACHE_TTL_SEC:
            return cached
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d", auto_adjust=False)
        if hist.empty or len(hist) < 1:
            return None
        last_close = float(hist["Close"].iloc[-1])
        pct = None
        if len(hist) >= 2:
            prev = float(hist["Close"].iloc[-2])
            if prev > 0:
                pct = (last_close / prev - 1.0) * 100.0
        # Try to get the display name + description — info call can be slow,
        # gated try/except. Includes longBusinessSummary for equities and a
        # similar description field for crypto when yfinance has one.
        name: str | None = None
        description: str | None = None
        try:
            info = t.info or {}
            name = info.get("shortName") or info.get("longName")
            description = (
                info.get("longBusinessSummary")
                or info.get("shortBusinessSummary")
                or info.get("description")
            )
        except Exception:
            pass
        result = {
            "name": name,
            "price": last_close,
            "pct_change_24h": pct,
            "description": description,
        }
        _yf_cache[ticker] = (now, result)
        return result
    except Exception:
        return None


@app.get("/search/tickers", response_model=list[TickerSearchResult])
def search_tickers(
    q: str = Query(min_length=1, max_length=20),
    include_external: bool = True,
) -> list[TickerSearchResult]:
    """Find tickers matching `q`. Searches our universe first (instant),
    then optionally falls back to yfinance for off-universe lookups."""
    q_upper = q.strip().upper()
    if not q_upper:
        return []

    results: list[TickerSearchResult] = []

    # 1) Local universe search — fast prefix match on base symbol
    with connect(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT u.symbol, u.base, u.asset_class,
                   o.close, o.pct_24h
            FROM universe u
            LEFT JOIN (
                SELECT symbol, asset_class,
                       LAST(close ORDER BY ts) AS close,
                       (LAST(close ORDER BY ts) /
                        NULLIF(FIRST(close ORDER BY ts), 0) - 1) * 100 AS pct_24h
                FROM ohlcv
                WHERE ts >= now() - INTERVAL '2 days'
                GROUP BY symbol, asset_class
            ) o ON o.symbol = u.symbol AND o.asset_class = u.asset_class
            WHERE u.included
              AND (upper(u.base) LIKE ? OR upper(u.symbol) LIKE ?)
            ORDER BY u."rank"
            LIMIT 8
            """,
            [f"{q_upper}%", f"{q_upper}%"],
        ).fetchall()

    seen_bases = set()
    for sym, base, ac, price, pct in rows:
        seen_bases.add(base.upper())
        results.append(TickerSearchResult(
            symbol=sym, base=base, asset_class=ac,
            price=float(price) if price is not None else None,
            pct_change_24h=float(pct) if pct is not None else None,
            in_universe=True,
        ))

    # 2) External fallback — yfinance first (stocks + major crypto with -USD),
    #    then CoinGecko for everything else (DEX-only / non-Binance.US alts).
    if include_external and q_upper not in seen_bases:
        ext = _yf_lookup(q_upper)
        # If yfinance returns NO price (often the case for off-yfinance alts),
        # fall through to CoinGecko which covers 13k+ coins.
        if ext is None or ext.get("price") is None:
            cg = _cg_lookup(q_upper)
            if cg is not None and cg.get("price") is not None:
                ext = cg  # use CoinGecko's payload instead
        if ext is not None and ext.get("price") is not None:
            full_desc = ext.get("description")
            short_desc = None
            if full_desc:
                # Truncate to ~280 chars for the dropdown so the row stays compact.
                short_desc = (
                    full_desc[:280].rsplit(" ", 1)[0] + "…"
                    if len(full_desc) > 280
                    else full_desc
                )
            results.append(TickerSearchResult(
                symbol=q_upper, base=q_upper, name=ext.get("name"),
                asset_class="external",
                price=ext.get("price"),
                pct_change_24h=ext.get("pct_change_24h"),
                in_universe=False,
                description=short_desc,
            ))

    return results


def _to_yf_symbol(base: str, asset_class: str) -> str:
    """Map our internal universe symbols to yfinance's lookup format.

    Equities: yfinance uses bare tickers (AAPL, MSFT) — same as our `base`.
    Crypto: yfinance uses `BTC-USD` while we store `BTC` in `base`.
    """
    if asset_class in ("crypto", "crypto_micro"):
        return f"{base}-USD"
    return base


class AskWhyResponse(BaseModel):
    symbol: str
    explanation: str
    asset_class: str
    enabled: bool = True


@app.get("/ticker/{symbol}/ask_why", response_model=AskWhyResponse)
def ticker_ask_why(
    symbol: str,
    asset_class: str = Query(...),
    user: User = Depends(require_pro),
) -> AskWhyResponse:
    """Pro-tier AI explanation of WHY a ticker is moving. Gated on the
    Anthropic API key being configured — returns 503 with a clear message
    when AI features are disabled, so the frontend can surface 'feature
    pending' instead of an opaque error."""
    from crypto_trends.ai import ask_why as ask_why_module
    from crypto_trends.ai import claude as claude_module

    if not claude_module.is_enabled():
        raise HTTPException(
            503,
            "AI features pending — ANTHROPIC_API_KEY not configured on this "
            "deployment. Coming soon.",
        )

    explanation = ask_why_module.ask_why(symbol, asset_class)
    if not explanation:
        raise HTTPException(
            424,  # Failed Dependency — Claude returned nothing useful
            "Not enough recent data to explain this ticker. Try a more-active name.",
        )

    return AskWhyResponse(
        symbol=symbol,
        explanation=explanation,
        asset_class=asset_class,
    )


@app.get("/ticker/{symbol}/description", response_model=TickerDescription)
def ticker_description(
    symbol: str,
    asset_class: str = Query(...),
) -> TickerDescription:
    """Long-form description for the drilldown modal. Lazy yfinance lookup,
    cached 1h. Works for both in-universe and external tickers — caller just
    needs to pass the asset_class so we can map the symbol correctly."""
    yf_sym = _to_yf_symbol(symbol, asset_class)
    ext = _yf_lookup(yf_sym)
    # If yfinance returns nothing useful and it's a crypto ticker, try CG.
    is_crypto = asset_class in ("crypto", "crypto_micro", "external")
    if (ext is None or not ext.get("description")) and is_crypto:
        cg = _cg_lookup(symbol)
        if cg is not None and cg.get("description"):
            ext = cg
    if ext is None:
        # Return empty (not 404) — the UI will just hide the section.
        return TickerDescription(
            symbol=symbol, name=None, description=None,
            fetched_at=datetime.utcnow(),
        )
    return TickerDescription(
        symbol=symbol,
        name=ext.get("name"),
        description=ext.get("description"),
        fetched_at=datetime.utcnow(),
    )


@app.get("/external/quote/{ticker}", response_model=ExternalQuote)
def external_quote(ticker: str) -> ExternalQuote:
    """Live quote for any ticker. yfinance first (stocks + major crypto),
    then CoinGecko fallback for off-yfinance alts. Used by the Watchlist
    tab to refresh prices for off-universe tickers."""
    ext = _yf_lookup(ticker)
    if ext is None or ext.get("price") is None:
        cg = _cg_lookup(ticker)
        if cg is not None and cg.get("price") is not None:
            ext = cg
    if ext is None or ext.get("price") is None:
        raise HTTPException(404, f"Ticker '{ticker}' not found on yfinance or CoinGecko.")
    return ExternalQuote(
        symbol=ticker.upper(),
        name=ext.get("name"),
        price=ext.get("price"),
        pct_change_24h=ext.get("pct_change_24h"),
        fetched_at=datetime.utcnow(),
        description=ext.get("description"),
    )
