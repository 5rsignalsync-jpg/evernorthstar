"use client";

import { useEffect, useState } from "react";
import { fetchFreshness, type FreshnessResponse } from "@/lib/api";

const POLL_INTERVAL_MS = 60_000;

const SEVERITY_COLORS = {
  green:
    "bg-emerald-400 ring-emerald-400/30",
  amber:
    "bg-amber-400 ring-amber-400/30",
  red:
    "bg-rose-400 ring-rose-400/30",
};

const SEVERITY_LABELS = {
  green: "Fresh",
  amber: "Aging",
  red: "Stale",
};

export function FreshnessIndicator() {
  const [data, setData] = useState<FreshnessResponse | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await fetchFreshness();
        if (!cancelled) setData(r);
      } catch {
        if (!cancelled) setData(null);
      }
    }
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (!data || data.asset_classes.length === 0) return null;

  const sev = data.worst_severity;
  const dot = SEVERITY_COLORS[sev];

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-[11px] text-zinc-400 hover:text-zinc-200"
        aria-label="Data freshness"
        title="Click for per-asset-class freshness"
      >
        <span className={`inline-block w-2 h-2 rounded-full ring-2 ${dot}`} />
        <span className="hidden sm:inline">Data</span>
        <span className="text-zinc-500">{SEVERITY_LABELS[sev]}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 z-30 w-72 rounded-md border border-zinc-700 bg-zinc-900 shadow-xl p-3">
          <div className="text-xs text-zinc-400 mb-2">
            Latest data per sleeve. Crypto refreshes every 15 min, equities
            hourly.
          </div>
          <ul className="text-[11px] divide-y divide-zinc-800">
            {data.asset_classes.map((ac) => {
              const isEquity = ac.asset_class.startsWith("equity");
              // Crypto expected freshness matches the 15-min intraday cron;
              // equities still ride the hourly window (yfinance rate limits
              // + FinBERT weight make a shorter cadence unsafe).
              const greenMax = isEquity ? 24 * 3600 : 30 * 60;
              const amberMax = isEquity ? 5 * 86400 : 6 * 3600;
              const age = ac.age_seconds === null ? Infinity : Math.max(0, ac.age_seconds);
              const acSev: "green" | "amber" | "red" =
                ac.age_seconds === null
                  ? "red"
                  : age < greenMax
                  ? "green"
                  : age < amberMax
                  ? "amber"
                  : "red";
              return (
                <li
                  key={ac.asset_class}
                  className="flex items-center justify-between py-1.5"
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={`inline-block w-1.5 h-1.5 rounded-full ${SEVERITY_COLORS[acSev]}`}
                    />
                    <span className="text-zinc-300">{ac.asset_class}</span>
                  </span>
                  <span className="text-zinc-500 tabular-nums">
                    {ac.age_human} ago
                  </span>
                </li>
              );
            })}
          </ul>
          {sev !== "green" && (
            <p className="text-[10px] text-zinc-500 mt-2 leading-snug border-t border-zinc-800 pt-2">
              {sev === "amber"
                ? "Some sleeves haven't refreshed in a few hours. Prices may be slightly out of date."
                : "Data is significantly stale. Prices on screen may be wrong — refresh hasn't run recently."}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
