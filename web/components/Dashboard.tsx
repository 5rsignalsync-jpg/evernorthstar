"use client";

import { useEffect, useState } from "react";
import {
  fetchRankings,
  SLEEVES,
  type RankingsResponse,
  type SleeveKey,
} from "@/lib/api";
import { AuthMenu } from "./AuthMenu";
import { useAuth } from "./AuthProvider";
import { FreshnessIndicator } from "./FreshnessIndicator";
import { OnboardingTour } from "./OnboardingTour";
import { RankingsTable } from "./RankingsTable";
import { SmartMoneyTab } from "./SmartMoneyTab";
import { SymbolDetailModal } from "./SymbolDetail";
import { TableSkeleton } from "./Skeleton";
import { WatchlistTab } from "./WatchlistTab";

const POLL_INTERVAL_MS = 60_000;

type TabKey = SleeveKey | "smart_money" | "watchlist";

const TAB_ORDER: TabKey[] = [
  "smart_money",
  "long_term",
  "equity_large",
  "equity_micro",
  "crypto",
  "crypto_micro",
  "watchlist",
];

const TAB_LABEL: Record<TabKey, string> = {
  smart_money: "Smart Money",
  long_term: "Long-Term Picks",
  equity_large: "Large Caps",
  equity_micro: "Penny Stocks",
  crypto: "Crypto",
  crypto_micro: "Crypto Micro",
  watchlist: "★ Watchlist",
};

const TAB_BLURB: Record<TabKey, string> = {
  smart_money:
    "Mirror famous investors' disclosed trades (Buffett, Burry, Ackman, Cathie Wood, Pelosi when she trades). 13F + Form 4 insider + Congress flows, lag-aware.",
  long_term:
    "Buy & hold picks blending quality, value, and 12-month momentum across the S&P 100. Monthly rebalance horizon.",
  equity_large:
    "Short-term momentum ranking across the S&P 100. Daily bars, ~5-day rebalance. Best-validated sleeve in the app right now.",
  equity_micro:
    "Sub-$5 names with $1M+ daily volume. High-spread sleeve — backtest models 75 bps slippage. Use with caution.",
  crypto:
    "Utility-focused major crypto — BTC, ETH, SOL, XRP, XLM, HBAR, LINK, ADA, UNI, GRT, etc. Memes (DOGE, PEPE, TRUMP, etc.) explicitly excluded — those live in Crypto Micro. Hourly cross-sectional momentum.",
  crypto_micro:
    "Lower-cap alts + memes — the moonshot sleeve. DOT, AAVE, APE, plus DOGE/SHIB/PEPE/TRUMP-style speculative names. Hourly bars, wider 60bps spread cost modeled. Survivorship bias in backtests is real here — treat as discovery, not signal.",
  watchlist:
    "Tickers you've starred. Stored locally in your browser (no account needed).",
};

export function Dashboard() {
  const { isPro, loading: authLoading } = useAuth();

  // Pro users land on Smart Money (where they get the most value).
  // Anonymous + free users land on Crypto (no gating, all 5 visible, hooks
  // immediately). Smart Money for free users is mostly "GATED" cards which
  // is a terrible first impression. Once auth resolves we pick the right tab,
  // but only on first paint — don't yank the user around if they navigated.
  const [tab, setTab] = useState<TabKey>("crypto");
  const [pickedInitial, setPickedInitial] = useState(false);
  useEffect(() => {
    if (authLoading || pickedInitial) return;
    if (isPro) setTab("smart_money");
    setPickedInitial(true);
  }, [authLoading, isPro, pickedInitial]);

  const [data, setData] = useState<RankingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  // When auth state flips (sign-in / sign-out / register), every data fetch
  // needs to re-fire so we don't show stale Pro data to a now-anonymous user
  // or stale Free data to a now-Pro user.
  useEffect(() => {
    const onAuthChange = () => {
      setData(null);
      setRefreshTick((x) => x + 1);
    };
    window.addEventListener("crypto-trends:auth-changed", onAuthChange);
    return () =>
      window.removeEventListener("crypto-trends:auth-changed", onAuthChange);
  }, []);

  const isSmartMoney = tab === "smart_money";
  const isWatchlist = tab === "watchlist";
  const sleeveKey =
    isSmartMoney || isWatchlist ? null : (tab as SleeveKey);

  useEffect(() => {
    if (!sleeveKey) {
      setData(null);
      return;
    }
    let cancelled = false;
    setData(null);
    setError(null);

    async function load() {
      try {
        const res = await fetchRankings(sleeveKey!);
        if (!cancelled) {
          setData(res);
          setError(null);
          setUpdatedAt(new Date());
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [sleeveKey, refreshTick]);

  const detailSignal =
    isSmartMoney || isWatchlist
      ? "momentum_v1"
      : SLEEVES[tab as SleeveKey].signal;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-8">
      <header className="max-w-5xl mx-auto mb-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-baseline flex-wrap gap-2">
            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">
              <span className="text-emerald-400">Ever</span>Northstar
            </h1>
            <span className="text-zinc-500 text-sm">
              · Honest signals. Smart money. Always pointing north. ⭐
            </span>
          </div>
          <div className="pt-1 shrink-0 flex items-center gap-4">
            <FreshnessIndicator />
            <AuthMenu />
          </div>
        </div>
        <p className="text-zinc-400 text-sm mt-2 max-w-3xl">
          Cross-sectional momentum across crypto, equities, and penny stocks ·
          13F + insider flows from 10 famous investors · Live FinBERT-scored news.
          Click any row for a chart + recent headlines. <span className="text-zinc-300">⭐</span> a ticker
          to track it in your watchlist.
        </p>
        <p className="text-[11px] text-amber-300/90 mt-2">
          <strong>Not financial advice.</strong> EverNorthstar is a research
          tool — backtests use realistic costs and the harness honestly tells you
          when a signal doesn&apos;t work. Trading carries substantial risk
          including total loss of principal.
        </p>
      </header>

      <nav
        className="max-w-5xl mx-auto mb-5 flex flex-wrap gap-2"
        aria-label="Asset class tabs"
      >
        {TAB_ORDER.map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={
              "px-3 py-1.5 text-sm rounded-md border transition-colors " +
              (k === tab
                ? "bg-zinc-100 text-zinc-900 border-zinc-100"
                : "bg-zinc-900 text-zinc-300 border-zinc-800 hover:bg-zinc-800")
            }
          >
            {TAB_LABEL[k]}
          </button>
        ))}
      </nav>

      <p className="max-w-5xl mx-auto text-xs text-zinc-500 mb-3">
        {TAB_BLURB[tab]}
      </p>

      {!isSmartMoney && !isWatchlist && (
        <div className="max-w-5xl mx-auto mb-3 flex items-center justify-between text-[11px] text-zinc-500">
          <span>
            {data ? (
              <>
                Signal: <code className="text-zinc-300">{data.signal_name}</code>{" "}
                · computed{" "}
                {new Date(data.computed_at + "Z").toLocaleString()}
              </>
            ) : (
              "Loading…"
            )}
          </span>
          <span className="flex items-center gap-3">
            {updatedAt && <>Polled {updatedAt.toLocaleTimeString()}</>}
            <button
              type="button"
              onClick={() => setRefreshTick((x) => x + 1)}
              className="px-2 py-0.5 border border-zinc-700 rounded text-zinc-400 hover:text-zinc-100 hover:border-zinc-500 transition-colors"
              aria-label="Refresh data now"
              title="Refresh now"
            >
              ↻ Refresh
            </button>
          </span>
        </div>
      )}

      {/* Per-sleeve caveats moved ABOVE tables so trust is established before data. */}
      {tab === "crypto_micro" && (
        <div className="max-w-5xl mx-auto mb-3 rounded-md border border-amber-700/40 bg-amber-900/10 px-4 py-2 text-xs text-amber-200">
          <strong>Micro-cap crypto caveat:</strong> wide spreads (~60 bps
          modeled), high manipulation risk, and severe survivorship bias —
          coins that died aren&apos;t in your dataset, so historical backtests
          are systematically optimistic. Treat as discovery, not signal.
        </div>
      )}
      {tab === "equity_micro" && (
        <div className="max-w-5xl mx-auto mb-3 rounded-md border border-amber-700/40 bg-amber-900/10 px-4 py-2 text-xs text-amber-200">
          <strong>Penny stocks caveat:</strong> high spreads (~75 bps modeled),
          manipulation risk, halt risk. Backtests show this sleeve loses money
          at retail execution costs — the harness is upfront about that.
        </div>
      )}
      {tab === "long_term" && (
        <div className="max-w-5xl mx-auto mb-3 rounded-md border border-amber-700/40 bg-amber-900/10 px-4 py-2 text-xs text-amber-200">
          <strong>Long-term caveat:</strong> scores use{" "}
          <em>current</em> fundamentals only — yfinance doesn't expose
          point-in-time history, so the backtest reflects price momentum
          alone. Treat as a current snapshot, not a validated strategy.
        </div>
      )}
      {tab === "smart_money" && (
        <div className="max-w-5xl mx-auto mb-3 rounded-md border border-amber-700/40 bg-amber-900/10 px-4 py-2 text-xs text-amber-200">
          <strong>Disclosure lag:</strong> 13F = 45 days after quarter-end ·
          Form 4 insiders = 2 days · Congress (STOCK Act) = 45 days legal max.
          The lag eats most short-term alpha; use as a confluence signal, not
          real-time copy-trading.
        </div>
      )}

      {error && !isSmartMoney && !isWatchlist && (
        <div className="max-w-5xl mx-auto mb-4 rounded-md border border-rose-700/40 bg-rose-900/20 px-4 py-3 text-sm text-rose-200 flex items-center justify-between gap-3">
          <span>API error: {error}.</span>
          <button
            type="button"
            onClick={() => setRefreshTick((x) => x + 1)}
            className="px-2 py-0.5 border border-rose-700/40 rounded text-rose-100 hover:bg-rose-900/40"
          >
            Retry
          </button>
        </div>
      )}

      {isWatchlist ? (
        <WatchlistTab onSelectSymbol={setSelectedSymbol} />
      ) : isSmartMoney ? (
        <SmartMoneyTab onSelectSymbol={setSelectedSymbol} />
      ) : !data && !error ? (
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
            <TableSkeleton rows={5} />
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
            <TableSkeleton rows={5} />
          </div>
        </div>
      ) : data?.long_only ? (
        <div className="max-w-5xl mx-auto">
          <RankingsTable
            title="Top Picks"
            side="long"
            rows={data.longs}
            onSelect={setSelectedSymbol}
            showLegend
            signalKind="momentum"
            assetClass={data.asset_class}
            upsellText={data.upsell_text}
          />
        </div>
      ) : (
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-4">
          <RankingsTable
            title="Top Longs"
            side="long"
            rows={data?.longs ?? []}
            onSelect={setSelectedSymbol}
            showLegend
            signalKind="momentum"
            assetClass={data?.asset_class ?? (tab as string)}
            upsellText={data?.upsell_text}
          />
          <RankingsTable
            title="Top Shorts"
            side="short"
            rows={data?.shorts ?? []}
            onSelect={setSelectedSymbol}
            signalKind="momentum"
            assetClass={data?.asset_class ?? (tab as string)}
          />
        </div>
      )}

      {selectedSymbol && (
        <SymbolDetailModal
          symbol={selectedSymbol}
          signal={detailSignal}
          onClose={() => setSelectedSymbol(null)}
        />
      )}

      <OnboardingTour />
    </main>
  );
}
