"use client";

/**
 * Search box for the Watchlist tab — type any ticker (AAPL, MSTR, GME, BTC,
 * a name from our sleeves, anything yfinance knows) and add it.
 *
 * Searches our local universe first (instant) then falls back to a yfinance
 * lookup for off-universe tickers. The yfinance lookup is cached server-side
 * for 1h to keep this snappy on repeat queries.
 */

import { useEffect, useRef, useState } from "react";
import {
  searchTickers,
  type TickerSearchResult,
} from "@/lib/api";
import { useWatchlist } from "@/hooks/useWatchlist";
import {
  EXTERNAL_ASSET_CLASS,
  isWatched as isWatchedKey,
} from "@/lib/watchlist";

const DEBOUNCE_MS = 300;

export function WatchlistSearch() {
  const { toggle, max, isAtLimit } = useWatchlist();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<number | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    if (!query.trim()) {
      setResults([]);
      setError(null);
      return;
    }
    setLoading(true);
    debounceRef.current = window.setTimeout(async () => {
      try {
        const res = await searchTickers(query);
        setResults(res);
        setError(null);
        setOpen(true);
      } catch (e) {
        setError(e instanceof Error ? e.message : "search failed");
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [query]);

  // Close dropdown on outside click
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!boxRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function addResult(r: TickerSearchResult) {
    // External lookups use a synthetic asset_class so we know to query
    // /external/quote for live price later instead of expecting a row in
    // our universe.
    const result = toggle({
      symbol: r.in_universe ? r.symbol : r.base,
      asset_class: r.in_universe ? r.asset_class : EXTERNAL_ASSET_CLASS,
      base: r.base,
      name: r.name ?? undefined,
    });
    if (result === "limit_reached") {
      setError(`Free tier limited to ${max} watchlist tickers. Upgrade to Pro for unlimited.`);
      return;
    }
    // Brief visual ack — close dropdown, clear query
    setQuery("");
    setResults([]);
    setOpen(false);
  }

  return (
    <div className="relative" ref={boxRef}>
      <div className="flex items-center gap-2 mb-1">
        <label htmlFor="watchlist-search" className="text-xs text-zinc-400">
          Add a ticker to your watchlist:
        </label>
        {isAtLimit && (
          <span className="text-[10px] text-amber-300/80">
            at free-tier limit ({max}) — upgrade for unlimited
          </span>
        )}
      </div>
      <input
        id="watchlist-search"
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder="e.g. AAPL, MSTR, GME, BTC, TSLA…"
        autoComplete="off"
        spellCheck={false}
        className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-zinc-500 outline-none"
      />

      {loading && (
        <div className="absolute right-3 top-[34px] text-[11px] text-zinc-500">
          Searching…
        </div>
      )}

      {open && (query.trim().length > 0) && (
        <div className="absolute z-20 mt-1 w-full bg-zinc-900 border border-zinc-700 rounded shadow-lg max-h-80 overflow-y-auto">
          {error && (
            <div className="px-3 py-2 text-xs text-rose-300">
              {error}
            </div>
          )}
          {!loading && !error && results.length === 0 && (
            <div className="px-3 py-3 text-xs text-zinc-500">
              No matches for &quot;{query}&quot;. Try a real ticker like AAPL or BTC.
            </div>
          )}
          {results.map((r) => {
            const alreadyWatched = isWatchedKey(
              r.in_universe ? r.symbol : r.base,
              r.in_universe ? r.asset_class : EXTERNAL_ASSET_CLASS,
            );
            return (
              <button
                key={`${r.asset_class}:${r.symbol}`}
                type="button"
                onClick={() => !alreadyWatched && addResult(r)}
                disabled={alreadyWatched || isAtLimit}
                className={
                  "w-full text-left px-3 py-2 border-b border-zinc-800 last:border-0 " +
                  (alreadyWatched
                    ? "opacity-50 cursor-not-allowed"
                    : isAtLimit
                    ? "opacity-50 cursor-not-allowed"
                    : "hover:bg-zinc-800/50 cursor-pointer")
                }
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-medium text-zinc-100">{r.base}</span>
                    {r.name && (
                      <span className="text-[11px] text-zinc-500 truncate">
                        {r.name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[11px] shrink-0">
                    {r.price !== null && (
                      <span className="font-mono text-zinc-300">
                        ${r.price < 1 ? r.price.toFixed(4) : r.price.toFixed(2)}
                      </span>
                    )}
                    {r.pct_change_24h !== null && (
                      <span
                        className={
                          "font-mono " +
                          (r.pct_change_24h >= 0
                            ? "text-emerald-400"
                            : "text-rose-400")
                        }
                      >
                        {r.pct_change_24h >= 0 ? "+" : ""}
                        {r.pct_change_24h.toFixed(2)}%
                      </span>
                    )}
                    {!r.in_universe && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-400">
                        external
                      </span>
                    )}
                    {alreadyWatched && (
                      <span className="text-amber-300">★</span>
                    )}
                  </div>
                </div>
                {r.description && (
                  <p className="text-[11px] text-zinc-500 mt-1 leading-snug line-clamp-2">
                    {r.description}
                  </p>
                )}
              </button>
            );
          })}
        </div>
      )}

      <p className="text-[10px] text-zinc-500 mt-1.5">
        Universe tickers are starred instantly. Off-universe lookups (e.g.
        MSTR, GME) take ~1s to validate via yfinance.
      </p>
    </div>
  );
}
