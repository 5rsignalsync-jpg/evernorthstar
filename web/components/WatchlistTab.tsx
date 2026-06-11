"use client";

import { useEffect, useMemo, useState } from "react";
import { useWatchlist } from "@/hooks/useWatchlist";
import {
  fetchExternalQuote,
  fetchRankings,
  type RankingRow,
  type SleeveKey,
  SLEEVES,
} from "@/lib/api";
import { EXTERNAL_ASSET_CLASS } from "@/lib/watchlist";
import { ScoreLegend } from "./ScoreLegend";
import { StarButton } from "./StarButton";
import { WatchlistSearch } from "./WatchlistSearch";

type WatchedRow = RankingRow & {
  asset_class: string;
  sleeve_signal: string;
  external?: boolean;
  display_name?: string;
};

function scoreColor(score: number): string {
  if (score > 0.5) return "text-emerald-400";
  if (score > 0.2) return "text-emerald-300";
  if (score < -0.5) return "text-rose-400";
  if (score < -0.2) return "text-rose-300";
  return "text-zinc-400";
}

function formatPrice(p: number | null): string {
  if (p === null) return "—";
  if (p < 0.01) return p.toFixed(6);
  if (p < 1) return p.toFixed(4);
  if (p < 100) return p.toFixed(2);
  return p.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function pctColor(pct: number | null): string {
  if (pct === null) return "text-zinc-500";
  if (pct > 0) return "text-emerald-400";
  if (pct < 0) return "text-rose-400";
  return "text-zinc-400";
}

function directionArrow(value: number | null): string {
  if (value === null || value === 0) return "·";
  return value > 0 ? "▲" : "▼";
}

const SLEEVE_BY_ASSET_CLASS: Record<string, SleeveKey | null> = {
  crypto: "crypto",
  equity_large: "equity_large",
  equity_micro: "equity_micro",
};

export function WatchlistTab({
  onSelectSymbol,
}: {
  onSelectSymbol: (symbol: string) => void;
}) {
  const { items } = useWatchlist();
  const [rows, setRows] = useState<WatchedRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Asset classes we need to fetch rankings for to look up current scores.
  const neededClasses = useMemo(() => {
    const set = new Set<string>();
    items.forEach((i) => set.add(i.asset_class));
    return Array.from(set);
  }, [items]);

  useEffect(() => {
    if (items.length === 0) {
      setRows([]);
      return;
    }
    let cancelled = false;

    async function load() {
      try {
        // 1) Fetch sleeve rankings for in-universe items so we can show score.
        const lookups = await Promise.all(
          neededClasses
            .filter((ac) => ac !== EXTERNAL_ASSET_CLASS)
            .map((ac) => SLEEVE_BY_ASSET_CLASS[ac])
            .filter((s): s is SleeveKey => s !== null && s !== undefined)
            .map(async (sleeve) => {
              try {
                const r = await fetchRankings(sleeve);
                return {
                  asset_class: SLEEVES[sleeve].assetClass,
                  signal: SLEEVES[sleeve].signal,
                  rows: [...r.longs, ...r.shorts],
                };
              } catch {
                return null;
              }
            }),
        );

        if (cancelled) return;

        const byKey = new Map<string, WatchedRow>();
        for (const lk of lookups) {
          if (!lk) continue;
          for (const row of lk.rows) {
            byKey.set(`${lk.asset_class}::${row.symbol}`, {
              ...row,
              asset_class: lk.asset_class,
              sleeve_signal: lk.signal,
            });
          }
        }

        // 2) For external (off-universe) tickers, fetch live yfinance quotes
        //    in parallel. These won't have score/rank — just price + 24h.
        const externalItems = items.filter((w) => w.asset_class === EXTERNAL_ASSET_CLASS);
        const externalQuotes = await Promise.all(
          externalItems.map(async (w) => {
            const ticker = w.base ?? w.symbol;
            const q = await fetchExternalQuote(ticker);
            return { item: w, quote: q };
          }),
        );

        if (cancelled) return;

        // Compose: matched in-universe rows + external quotes + still-missing
        // in-universe (e.g., user starred a ticker that fell out of the top-N
        // since they starred it).
        const matched: WatchedRow[] = items
          .filter((w) => w.asset_class !== EXTERNAL_ASSET_CLASS)
          .map((w) => byKey.get(`${w.asset_class}::${w.symbol}`))
          .filter((r): r is WatchedRow => Boolean(r));

        const externals: WatchedRow[] = externalQuotes.map(({ item, quote }) => ({
          symbol: item.base ?? item.symbol,
          base: item.base ?? item.symbol,
          score: 0,
          rank: 9999,
          price: quote?.price ?? null,
          pct_change_24h: quote?.pct_change_24h ?? null,
          components: null,
          headline: null,
          headline_publisher: null,
          headline_at: null,
          news_buzz: null,
          news_sentiment: null,
          negative_event: false,
          upcoming_earnings: null,
          days_to_earnings: null,
          asset_class: EXTERNAL_ASSET_CLASS,
          sleeve_signal: "external",
          external: true,
          display_name: item.name ?? quote?.name ?? undefined,
        }));

        // 3) For in-universe items that fell OUT of the current top-N (e.g.,
        //    user starred WOD when it was #2, now it's #8 and didn't come
        //    back in the rankings), enrich them with a live quote via the
        //    same yfinance+CoinGecko fallback chain we use for externals.
        //    This prevents "no price" rows in the watchlist purely because
        //    something fell out of view in the rankings.
        const missingItems = items.filter(
          (w) =>
            w.asset_class !== EXTERNAL_ASSET_CLASS &&
            !byKey.has(`${w.asset_class}::${w.symbol}`),
        );
        const missingQuotes = await Promise.all(
          missingItems.map(async (w) => {
            const ticker = w.base ?? w.symbol;
            const q = await fetchExternalQuote(ticker);
            return { item: w, quote: q };
          }),
        );

        if (cancelled) return;

        const missing: WatchedRow[] = missingQuotes.map(({ item, quote }) => ({
          symbol: item.symbol,
          base: item.base ?? item.symbol,
          score: 0,
          rank: 9999,
          price: quote?.price ?? null,
          pct_change_24h: quote?.pct_change_24h ?? null,
          components: null,
          headline: null,
          headline_publisher: null,
          headline_at: null,
          news_buzz: null,
          news_sentiment: null,
          negative_event: false,
          upcoming_earnings: null,
          days_to_earnings: null,
          asset_class: item.asset_class,
          sleeve_signal: "momentum_v1",
          display_name: quote?.name ?? undefined,
        }));

        setRows([...matched, ...externals, ...missing]);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [items, neededClasses]);

  if (items.length === 0) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <WatchlistSearch />
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-8 text-center">
          <p className="text-2xl mb-2">☆</p>
          <h2 className="text-lg font-medium text-zinc-200 mb-1">
            Your watchlist is empty.
          </h2>
          <p className="text-sm text-zinc-500 max-w-md mx-auto">
            Search above to add any ticker — or star one from any other tab.
            Stored locally in your browser (no account needed).
          </p>
        </div>
      </div>
    );
  }

  const tickerCountLabel = items.length === 1 ? "1 ticker" : `${items.length} tickers`;

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
        <WatchlistSearch />
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold text-zinc-100">
            Your watchlist
          </h2>
          <span className="text-xs text-zinc-500">{tickerCountLabel}</span>
        </div>
        <ScoreLegend kind="momentum" />

        {error && (
          <p className="text-xs text-rose-300 mb-2">Failed to load: {error}</p>
        )}

        <table className="w-full text-sm">
          <thead>
            <tr className="text-zinc-500 text-xs uppercase tracking-wider">
              <th className="text-left font-normal py-2 w-6"></th>
              <th className="text-left font-normal py-2">Ticker</th>
              <th className="text-left font-normal py-2">Asset class</th>
              <th className="text-right font-normal py-2">Price</th>
              <th className="text-right font-normal py-2">24h</th>
              <th className="text-right font-normal py-2">Score</th>
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map((r) => (
              <tr
                key={`${r.asset_class}::${r.symbol}`}
                className="border-t border-zinc-800/60 cursor-pointer hover:bg-zinc-800/30"
                onClick={() => onSelectSymbol(r.symbol)}
                title="Click for chart + headlines"
              >
                <td className="py-2" onClick={(e) => e.stopPropagation()}>
                  <StarButton
                    symbol={r.symbol}
                    asset_class={r.asset_class}
                    base={r.base}
                  />
                </td>
                <td className="py-2 text-zinc-100 font-medium">
                  {r.base}
                  {r.display_name && (
                    <span className="text-[10px] text-zinc-500 ml-2 font-normal">
                      {r.display_name.length > 24
                        ? r.display_name.slice(0, 22) + "…"
                        : r.display_name}
                    </span>
                  )}
                </td>
                <td className="py-2 text-zinc-500 text-xs">
                  {r.external ? (
                    <span title="External ticker — looked up via yfinance, not in our ranking universe">
                      external
                    </span>
                  ) : (
                    r.asset_class.replace("_", " ")
                  )}
                </td>
                <td className="py-2 text-right text-zinc-300 tabular-nums">
                  ${formatPrice(r.price)}
                </td>
                <td
                  className={`py-2 text-right tabular-nums ${pctColor(r.pct_change_24h)}`}
                >
                  <span aria-hidden="true" className="text-[10px] mr-0.5">
                    {directionArrow(r.pct_change_24h)}
                  </span>
                  {r.pct_change_24h === null
                    ? "—"
                    : `${r.pct_change_24h >= 0 ? "+" : ""}${r.pct_change_24h.toFixed(2)}%`}
                </td>
                <td
                  className={`py-2 text-right tabular-nums font-medium ${scoreColor(r.score)}`}
                >
                  {r.external ? (
                    <span className="text-zinc-600 text-xs italic">
                      no ranking
                    </span>
                  ) : r.rank === 9999 ? (
                    <span className="text-zinc-600 text-xs italic">
                      not in current top
                    </span>
                  ) : (
                    <>
                      {r.score >= 0 ? "+" : ""}
                      {r.score.toFixed(3)}
                    </>
                  )}
                </td>
              </tr>
            ))}
            {rows === null && (
              <tr>
                <td colSpan={6} className="py-4 text-center text-zinc-500 text-xs">
                  Loading…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-[11px] text-zinc-600 mt-3 leading-relaxed">
        Watchlist is stored in your browser only — nothing is sent to the server.
        Clearing your browser data will reset it. Account-backed sync across
        devices is on the roadmap.
      </p>
    </div>
  );
}
