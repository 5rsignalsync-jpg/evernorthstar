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

// ---------------- AI: Earnings summary ----------------

export type EarningsSummaryResult =
  | {
      status: "ok";
      summary: string;
      earnings_date: string;
      cached: boolean;
      model_version: string | null;
    }
  | { status: "pending"; message: string }
  | { status: "free_tier"; message: string }
  | { status: "no_data"; message: string }
  | { status: "error"; message: string };

export async function fetchEarningsSummary(
  symbol: string,
): Promise<EarningsSummaryResult> {
  const res = await fetch(
    `${BASE}/ticker/${encodeURIComponent(symbol)}/earnings_summary`,
    { cache: "no-store", credentials: "include" },
  );
  if (res.ok) {
    const data = await res.json();
    return {
      status: "ok",
      summary: data.summary,
      earnings_date: data.earnings_date,
      cached: !!data.cached,
      model_version: data.model_version ?? null,
    };
  }
  if (res.status === 503) {
    return { status: "pending", message: "AI earnings summaries coming soon." };
  }
  if (res.status === 402 || res.status === 403) {
    return { status: "free_tier", message: "Earnings AI is a Pro feature." };
  }
  if (res.status === 404) {
    return {
      status: "no_data",
      message: "No recent earnings event with usable data found for this ticker.",
    };
  }
  return { status: "error", message: `Earnings summary failed (${res.status})` };
}

// ---------------- AI: Ask Why ----------------

export type AskWhyResponse = {
  symbol: string;
  explanation: string;
  asset_class: string;
};

export type AskWhyResult =
  | { status: "ok"; explanation: string }
  | { status: "pending"; message: string }      // 503 — Anthropic key not configured
  | { status: "free_tier"; message: string }    // 402 / 403 — Pro-gated
  | { status: "thin_data"; message: string }    // 424 — not enough data
  | { status: "error"; message: string };       // anything else

export async function fetchAskWhy(
  symbol: string,
  assetClass: string,
): Promise<AskWhyResult> {
  const params = new URLSearchParams({ asset_class: assetClass });
  const res = await fetch(
    `${BASE}/ticker/${encodeURIComponent(symbol)}/ask_why?${params}`,
    { cache: "no-store", credentials: "include" },
  );
  if (res.ok) {
    const data: AskWhyResponse = await res.json();
    return { status: "ok", explanation: data.explanation };
  }
  if (res.status === 503) {
    return {
      status: "pending",
      message: "AI explanations are coming soon — feature wired up but the deployment hasn't been provisioned with an Anthropic API key yet.",
    };
  }
  if (res.status === 402 || res.status === 403) {
    return {
      status: "free_tier",
      message: "AI 'Ask Why' is a Pro feature. Upgrade to unlock.",
    };
  }
  if (res.status === 424) {
    return {
      status: "thin_data",
      message: "Not enough recent data to explain this ticker. Try a more-active name.",
    };
  }
  let msg = `Ask Why failed (${res.status})`;
  try {
    const body = await res.json();
    if (body?.detail) msg = String(body.detail);
  } catch {
    /* ignore */
  }
  return { status: "error", message: msg };
}

// ---------------- Portfolio (Plaid brokerage sync) ----------------

export type BrokerageAccount = {
  id: number;
  institution_name: string;
  status: string;
  last_synced_at: string | null;
  last_error: string | null;
  created_at: string;
};

export type AnnotatedHolding = {
  id: number | null;
  ticker: string | null;
  name: string;
  security_type: string | null;
  quantity: number;
  value: number | null;
  cost_basis: number | null;
  institution_name: string;
  momentum_score: number | null;
  asset_class: string | null;
  smart_money_actors: string[];
  smart_money_buys_usd: number;
  smart_money_sells_usd: number;
};

export type PortfolioSummary = {
  total_value_usd: number;
  n_holdings: number;
  n_with_signal: number;
  n_with_smart_money: number;
  weighted_momentum_score: number | null;
  smart_money_overlap_pct: number;
  momentum_quality_label: "strong" | "mixed" | "weak" | "unscored";
};

export type PortfolioResponse = {
  summary: PortfolioSummary;
  holdings: AnnotatedHolding[];
  accounts: BrokerageAccount[];
  plaid_enabled: boolean;
};

export async function fetchPortfolio(): Promise<PortfolioResponse> {
  const res = await fetch(`${BASE}/portfolio`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Portfolio fetch failed: ${res.status}`);
  return res.json();
}

export async function createPlaidLinkToken(): Promise<{ link_token: string; env: string }> {
  const res = await fetch(`${BASE}/portfolio/link-token`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function exchangePlaidPublicToken(
  publicToken: string,
): Promise<BrokerageAccount> {
  const res = await fetch(`${BASE}/portfolio/exchange-token`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ public_token: publicToken }),
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function disconnectBrokerage(accountId: number): Promise<void> {
  const res = await fetch(`${BASE}/portfolio/accounts/${accountId}`, {
    method: "DELETE",
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok && res.status !== 204) {
    throw new Error(`Disconnect failed: ${res.status}`);
  }
}

export async function syncBrokerage(accountId: number): Promise<BrokerageAccount> {
  const res = await fetch(`${BASE}/portfolio/sync/${accountId}`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Sync failed: ${res.status}`);
  return res.json();
}

// ---------------- Position planning (Sprint 1 + 2) ----------------

export type ZoneName =
  | "accumulation"
  | "neutral"
  | "distribution"
  | "extreme_distribution";

export type ZoneReading = {
  zone: ZoneName;
  zone_confidence: number;
  rsi: number | null;
  bb_position_sigma: number | null;
  score_percentile: number | null;
  volume_divergence: boolean;
  accumulation_low: number | null;
  accumulation_high: number | null;
  distribution_low: number | null;
  distribution_high: number | null;
  current_price: number | null;
};

export type RingFenceScenario = {
  pct_of_gain_locked: number;
  amount_to_take_usd: number;
  remaining_position_value: number;
  net_pl_if_remainder_zero_usd: number;
};

export type HistoricalOutcome = {
  ticker: string;
  setup_date: string;
  setup_price: number;
  fwd_30d_return_pct: number | null;
  fwd_90d_return_pct: number | null;
};

export type HistoricalStats = {
  n_setups: number;
  median_fwd_30d_return_pct: number | null;
  median_fwd_90d_return_pct: number | null;
  p25_fwd_30d_return_pct: number | null;
  p75_fwd_30d_return_pct: number | null;
  sample: HistoricalOutcome[];
};

export type EntryTranche = {
  label: string;
  price: number;
  pct_of_budget: number;
  amount_usd: number | null;
  quantity: number | null;
};

export type EntryPlan = {
  status: "in_zone" | "above_zone" | "below_zone" | "unknown";
  accumulation_low: number;
  accumulation_high: number;
  invalidation_level: number;
  tranches: EntryTranche[];
  note: string;
};

export type PositionPlan = {
  symbol: string;
  base: string;
  asset_class: string;
  quantity: number;
  cost_basis_per_share: number | null;
  current_price: number | null;
  current_value: number | null;
  unrealized_gain_usd: number | null;
  unrealized_gain_pct: number | null;
  zone: ZoneReading;
  ring_fence_scenarios: RingFenceScenario[];
  entry_plan: EntryPlan | null;
  historical: HistoricalStats | null;
  ai_summary: string | null;
  ai_enabled: boolean;
  disclaimer: string;
};

export async function fetchHoldingPlan(
  holdingId: number,
  opts?: { withAi?: boolean },
): Promise<PositionPlan> {
  const params = new URLSearchParams();
  if (opts?.withAi) params.set("with_ai", "true");
  const q = params.toString();
  const url = `${BASE}/portfolio/holdings/${holdingId}/plan${q ? `?${q}` : ""}`;
  const res = await fetch(url, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) {
    let msg = `Plan fetch failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function fetchSymbolPlan(
  symbol: string,
  opts?: { quantity?: number; costBasisPerShare?: number; withAi?: boolean },
): Promise<PositionPlan> {
  const params = new URLSearchParams();
  if (opts?.quantity !== undefined) params.set("quantity", String(opts.quantity));
  if (opts?.costBasisPerShare !== undefined)
    params.set("cost_basis_per_share", String(opts.costBasisPerShare));
  if (opts?.withAi) params.set("with_ai", "true");
  const q = params.toString();
  const url = `${BASE}/portfolio/plan/${encodeURIComponent(symbol)}${q ? `?${q}` : ""}`;
  const res = await fetch(url, { cache: "no-store", credentials: "include" });
  if (!res.ok) {
    let msg = `Plan fetch failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

// ---------------- Alert rules ----------------

export type AlertCondition =
  | "score_above"
  | "score_below"
  | "price_above"
  | "price_below"
  | "zone_target";

export type ZoneTarget = "accumulation" | "distribution" | "extreme_distribution";

export type AlertRule = {
  id: number;
  symbol: string;
  asset_class: string;
  condition: AlertCondition;
  threshold: number;
  zone_target: ZoneTarget | null;
  note: string | null;
  enabled: boolean;
  created_at: string;
  last_triggered_at: string | null;
};

export type AlertEvent = {
  id: number;
  rule_id: number;
  triggered_at: string;
  observed_value: number;
  email_sent: boolean;
};

export async function listAlertRules(): Promise<AlertRule[]> {
  const res = await fetch(`${BASE}/alerts`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`List alerts failed: ${res.status}`);
  return res.json();
}

export async function createAlertRule(
  rule: Omit<AlertRule, "id" | "created_at" | "last_triggered_at" | "enabled"> & {
    enabled?: boolean;
  },
): Promise<AlertRule> {
  const res = await fetch(`${BASE}/alerts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ enabled: true, ...rule }),
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function deleteAlertRule(id: number): Promise<void> {
  const res = await fetch(`${BASE}/alerts/${id}`, {
    method: "DELETE",
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok && res.status !== 204) {
    throw new Error(`Delete alert failed: ${res.status}`);
  }
}

export async function toggleAlertRule(
  id: number,
  enabled: boolean,
): Promise<AlertRule> {
  const params = new URLSearchParams({ enabled: String(enabled) });
  const res = await fetch(`${BASE}/alerts/${id}?${params}`, {
    method: "PATCH",
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Toggle alert failed: ${res.status}`);
  return res.json();
}

export async function listAlertEvents(limit = 20): Promise<AlertEvent[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  const res = await fetch(`${BASE}/alerts/events?${params}`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`List alert events failed: ${res.status}`);
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
