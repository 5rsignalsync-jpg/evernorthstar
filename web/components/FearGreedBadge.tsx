"use client";

/**
 * Crypto Fear & Greed Index badge — small chip in the dashboard header.
 *
 * Sourced from alternative.me (the canonical crypto F&G publisher). Backend
 * caches 1h to avoid hammering the upstream.
 *
 * Color logic:
 *   0–25   Extreme Fear     → rose (red — sentiment crash, contrarian buy zone)
 *   26–46  Fear             → amber (cautious)
 *   47–54  Neutral          → zinc (neither)
 *   55–75  Greed            → emerald (sentiment hot)
 *   76–100 Extreme Greed    → amber (warning — sentiment frothy, contrarian sell)
 *
 * Both extremes use warning colors (rose / amber) so the badge always reads
 * "pay attention" at the edges, even though one is the buy zone and one is
 * the sell zone — the classification text clarifies which.
 */

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type MarketMood = {
  value: number;
  classification: string;
  fetched_at: string;
  source: string;
  asset_class: string;
};

function colorClasses(value: number): string {
  if (value <= 25) return "text-rose-200 border-rose-700/50 bg-rose-900/30";
  if (value <= 46) return "text-amber-200 border-amber-700/50 bg-amber-900/30";
  if (value <= 54) return "text-zinc-300 border-zinc-600/60 bg-zinc-800/50";
  if (value <= 75) return "text-emerald-200 border-emerald-700/50 bg-emerald-900/30";
  return "text-amber-200 border-amber-700/50 bg-amber-900/30";
}

export function FearGreedBadge() {
  const [mood, setMood] = useState<MarketMood | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/status/market_mood`, {
          cache: "no-store",
        });
        if (!res.ok) {
          setError(`${res.status}`);
          return;
        }
        const data = (await res.json()) as MarketMood;
        setMood(data);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "fetch failed");
      }
    }
    load();
    // 30-min refresh (backend itself caches 1h, but UI polling keeps it warm
    // if a tab stays open for many hours)
    const id = setInterval(load, 30 * 60_000);
    return () => clearInterval(id);
  }, []);

  if (error || !mood) return null;

  const fetched = new Date(mood.fetched_at + "Z");
  const tooltip =
    `Crypto Fear & Greed Index: ${mood.value} (${mood.classification})\n` +
    `Source: alternative.me · Updated: ${fetched.toLocaleString()}\n` +
    `Composite of crypto market volatility, momentum, social media, dominance, and Google trends.`;

  return (
    <div
      className={
        "text-[11px] px-2 py-1 rounded-md border whitespace-nowrap " +
        colorClasses(mood.value)
      }
      title={tooltip}
    >
      <span className="opacity-75">F&amp;G</span>{" "}
      <span className="font-mono font-medium">{mood.value}</span>{" "}
      <span className="opacity-75 hidden sm:inline">
        · {mood.classification}
      </span>
    </div>
  );
}
