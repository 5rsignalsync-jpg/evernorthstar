"use client";

import { useEffect, useMemo, useState } from "react";
import { useWatchlist } from "@/hooks/useWatchlist";
import {
  fetchRankings,
  type RankingRow,
  type SleeveKey,
  SLEEVES,
} from "@/lib/api";
import { ScoreLegend } from "./ScoreLegend";
import { StarButton } from "./StarButton";

type WatchedRow = RankingRow & {
  asset_class: string;
  sleeve_signal: string;
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
        // Fetch each sleeve's rankings (top 25 to maximize chance of hit).
        const lookups = await Promise.all(
          neededClasses
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

        const matched: WatchedRow[] = items
          .map((w) => byKey.get(`${w.asset_class}::${w.symbol}`))
          .filter((r): r is WatchedRow => Boolean(r));

        // Surface any watched symbols we couldn't find in current rankings.
        const missing = items
          .filter((w) => !byKey.has(`${w.asset_class}::${w.symbol}`))
          .map<WatchedRow>((w) => ({
            symbol: w.symbol,
            base: w.base ?? w.symbol,
            score: 0,
            rank: 9999,
            price: null,
            pct_change_24h: null,
            components: null,
            headline: null,
            headline_publisher: null,
            headline_at: null,
            news_buzz: null,
            news_sentiment: null,
            negative_event: false,
            // Earnings overlay only fires when this ticker shows up in a live
            // ranking. Watchlist-only rows have no earnings context — null is
            // the right placeholder.
            upcoming_earnings: null,
            days_to_earnings: null,
            asset_class: w.asset_class,
            sleeve_signal: "momentum_v1",
          }));

        setRows([...matched, ...missing]);
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
      <div className="max-w-5xl mx-auto rounded-lg border border-zinc-800 bg-zinc-900/40 p-8 text-center">
        <p className="text-2xl mb-2">☆</p>
        <h2 className="text-lg font-medium text-zinc-200 mb-1">
          Your watchlist is empty.
        </h2>
        <p className="text-sm text-zinc-500 max-w-md mx-auto">
          Click the star next to any ticker on the other tabs to add it here.
          The watchlist persists across sessions on this device.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold text-zinc-100">
            Your watchlist
          </h2>
          <span className="text-xs text-zinc-500">{items.length} tickers</span>
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
                <td className="py-2 text-zinc-100 font-medium">{r.base}</td>
                <td className="py-2 text-zinc-500 text-xs">
                  {r.asset_class.replace("_", " ")}
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
                  {r.rank === 9999 ? (
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
        Clearing your browser data will reset it. We&apos;ll add account-backed
        sync once auth is wired.
      </p>
    </div>
  );
}
