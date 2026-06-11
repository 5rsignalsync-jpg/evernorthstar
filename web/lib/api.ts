export type RankingRow = {
  symbol: string;
  base: string;
  score: number;
  rank: number;
  price: number | null;
  pct_change_24h: number | null;
  components: Record<string, number | null> | null;
  headline: string | null;
  headline_publisher: string | null;
  headline_at: string | null;
  news_buzz: number | null;
  news_sentiment: number | null;
  negative_event: boolean;
  upcoming_earnings: string | null;
  days_to_earnings: number | null;
};

export type RankingsResponse = {
  signal_name: string;
  asset_class: string;
  long_only: boolean;
  computed_at: string;
  longs: RankingRow[];
  shorts: RankingRow[];
  tier: "free" | "pro";
  requested_top_n: number;
  delivered_top_n: number;
  upsell_text: string | null;
  disclaimer: string;
};

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type SleeveKey =
  | "crypto"
  | "crypto_micro"
  | "equity_large"
  | "equity_micro"
  | "long_term";

export const SLEEVES: Record<
  SleeveKey,
  { label: string; assetClass: string; signal: string; topN: number; horizon: string }
> = {
  crypto: {
    label: "Crypto",
    assetClass: "crypto",
    signal: "momentum_v1",
    topN: 25,
    horizon: "Short-term · hourly bars",
  },
  crypto_micro: {
    label: "Crypto Micro",
    assetClass: "crypto_micro",
    signal: "momentum_v1",
    topN: 25,
    horizon: "Low-cap alts · hourly · wider spreads (60bps modeled)",
  },
  equity_large: {
    label: "Large Caps",
    assetClass: "equity_large",
    signal: "momentum_v1",
    topN: 25,
    horizon: "Short-term · daily bars",
  },
  equity_micro: {
    label: "Penny Stocks",
    assetClass: "equity_micro",
    signal: "momentum_v1",
    // 25 here matches the Pro promise on /pricing. Penny screener only yields
    // ~12-15 candidates anyway, so this returns "all that pass the filter."
    topN: 25,
    horizon: "Short-term · daily bars · high-spread cost",
  },
  long_term: {
    label: "Long-Term Picks",
    assetClass: "equity_large",
    signal: "long_term_v1",
    topN: 25,
    horizon: "Buy/hold · quality + value + momentum · monthly rebalance",
  },
};

export async function fetchRankings(sleeve: SleeveKey): Promise<RankingsResponse> {
  const { assetClass, signal, topN } = SLEEVES[sleeve];
  const params = new URLSearchParams({
    asset_class: assetClass,
    signal_name: signal,
    top_n: String(topN),
  });
  const res = await fetch(`${BASE}/rankings?${params}`, {
    cache: "no-store",
    credentials: "include",   // pass session cookie for tier resolution
  });
  if (!res.ok) throw new Error(`Rankings ${sleeve} failed: ${res.status}`);
  return res.json();
}

export type HistoryPoint = {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  score: number | null;
};

export type HistoryHeadline = {
  ts: string;
  headline: string;
  publisher: string | null;
  url: string | null;
  sentiment: number | null;
};

export type SymbolDetail = {
  symbol: string;
  base: string;
  asset_class: string;
  interval: string;
  price_series: HistoryPoint[];
  headlines: HistoryHeadline[];
  disclaimer: string;
};

export type AssetClassFreshness = {
  asset_class: string;
  latest_bar: string | null;
  age_seconds: number | null;
  age_human: string;
};

export type FreshnessResponse = {
  asset_classes: AssetClassFreshness[];
  worst_severity: "green" | "amber" | "red";
};

export async function fetchFreshness(): Promise<FreshnessResponse> {
  const res = await fetch(`${BASE}/status/freshness`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Freshness fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchSymbolDetail(
  symbol: string,
  days = 90,
  signal = "momentum_v1",
): Promise<SymbolDetail> {
  const params = new URLSearchParams({ days: String(days), signal_name: signal });
  const res = await fetch(`${BASE}/history/${encodeURIComponent(symbol)}?${params}`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`History ${symbol} failed: ${res.status}`);
  return res.json();
}

// ---------------- Ticker search + external quotes ----------------

export type TickerSearchResult = {
  symbol: string;
  base: string;
  name: string | null;
  asset_class: string;
  price: number | null;
  pct_change_24h: number | null;
  in_universe: boolean;
  description: string | null;
};

export type TickerDescription = {
  symbol: string;
  name: string | null;
  description: string | null;
  fetched_at: string;
};

export async function fetchTickerDescription(
  symbol: string,
  asset_class: string,
): Promise<TickerDescription | null> {
  const params = new URLSearchParams({ asset_class });
  const res = await fetch(
    `${BASE}/ticker/${encodeURIComponent(symbol)}/description?${params}`,
    { cache: "no-store" },
  );
  if (!res.ok) return null;
  return res.json();
}

export async function searchTickers(query: string): Promise<TickerSearchResult[]> {
  const q = query.trim();
  if (!q) return [];
  const params = new URLSearchParams({ q, include_external: "true" });
  const res = await fetch(`${BASE}/search/tickers?${params}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export type ExternalQuote = {
  symbol: string;
  name: string | null;
  price: number | null;
  pct_change_24h: number | null;
  fetched_at: string;
  description: string | null;
};

export async function fetchExternalQuote(ticker: string): Promise<ExternalQuote | null> {
  const res = await fetch(
    `${BASE}/external/quote/${encodeURIComponent(ticker)}`,
    { cache: "no-store" },
  );
  if (!res.ok) return null;  // 404 = ticker doesn't exist, swallow it
  return res.json();
}

// ---------------- Smart Money ----------------

export type SmartMoneyActor = {
  actor_name: string;
  source: string;
  side: string;
  amount: number | null;
  disclosure_date: string | null;
};

export type SmartMoneyLeader = {
  ticker: string;
  score: number;
  n_funds_holding: number;
  total_13f_value_usd: number;
  insider_buys_usd: number;
  insider_sells_usd: number;
  insider_net_usd: number;
  congress_buys_usd: number;
  congress_sells_usd: number;
  top_actors: SmartMoneyActor[];
};

export type SmartMoneyResponse = {
  window_days: number;
  top_n: number;
  leaders: SmartMoneyLeader[];
  tier: "free" | "pro";
  requested_top_n: number;
  delivered_top_n: number;
  upsell_text: string | null;
  disclaimer: string;
};

export type ActorSummary = {
  actor_id: string;
  actor_name: string;
  actor_role: string | null;
  source: string;
  n_trades: number;
  last_disclosed: string | null;
};

export type ActorPosition = {
  ticker: string;
  source: string;
  side: string;
  last_disclosed: string | null;
  amount_min: number | null;
  amount_max: number | null;
  shares: number | null;
};

export type ActorBasket = {
  actor_id: string;
  positions: ActorPosition[];
};

export async function fetchSmartMoneyLeaders(
  windowDays = 90,
  topN = 25,
): Promise<SmartMoneyResponse> {
  const params = new URLSearchParams({
    window_days: String(windowDays),
    top_n: String(topN),
  });
  const res = await fetch(`${BASE}/smart_money/leaders?${params}`, { cache: "no-store", credentials: "include" });
  if (!res.ok) throw new Error(`Smart money leaders failed: ${res.status}`);
  return res.json();
}

export async function fetchSmartMoneyActors(): Promise<ActorSummary[]> {
  const res = await fetch(`${BASE}/smart_money/actors`, { cache: "no-store", credentials: "include" });
  if (!res.ok) throw new Error(`Smart money actors failed: ${res.status}`);
  return res.json();
}

export async function fetchActorBasket(actorId: string): Promise<ActorBasket> {
  const res = await fetch(
    `${BASE}/smart_money/actors/${encodeURIComponent(actorId)}`,
    { cache: "no-store", credentials: "include" },
  );
  if (!res.ok) throw new Error(`Actor ${actorId} failed: ${res.status}`);
  return res.json();
}

// ---------------- Strategies (Autopilot-style curated baskets) ----------------

export type StrategyPerformance = {
  since: string;
  days_held: number;
  strategy_return_pct: number;
  tickers_priced: number;
  tickers_unpriced: number;
};

export type StrategyCard = {
  slug: string;
  name: string;
  emoji: string;
  description: string;
  caveats: string[];
  ready: boolean;
  gated_reason: string | null;
  n_positions: number;
  last_activity: string | null;
  performance: StrategyPerformance | null;
};

export type StrategyPosition = {
  ticker: string;
  weight: number;
  value_usd: number;
  suggested_usd: number;
  note: string | null;
};

export type StrategyActivity = {
  ticker: string;
  actor_name: string;
  side: string;
  amount_usd: number | null;
  disclosure_date: string;
  source: string;
  note: string | null;
};

export type StrategyDetail = {
  card: StrategyCard;
  inverse: boolean;
  portfolio_size: number;
  positions: StrategyPosition[];
  recent_activity: StrategyActivity[];
  disclaimer: string;
};

export async function fetchStrategies(): Promise<StrategyCard[]> {
  const res = await fetch(`${BASE}/strategies`, { cache: "no-store", credentials: "include" });
  if (!res.ok) throw new Error(`Strategies list failed: ${res.status}`);
  return res.json();
}

export async function fetchStrategyDetail(
  slug: string,
  portfolioSize = 10_000,
): Promise<StrategyDetail> {
  const params = new URLSearchParams({ portfolio_size: String(portfolioSize) });
  const res = await fetch(
    `${BASE}/strategies/${encodeURIComponent(slug)}?${params}`,
    { cache: "no-store", credentials: "include" },
  );
  if (!res.ok) throw new Error(`Strategy ${slug} failed: ${res.status}`);
  return res.json();
}
