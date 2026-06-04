/**
 * Score legend shown above ranking tables. Explains the scale + color buckets
 * so a first-time user can interpret "+0.83" vs "+0.21" without context.
 *
 * Compact by default; clickable to expand into a fuller explanation.
 */

"use client";

import { useState } from "react";

export function ScoreLegend({ kind = "momentum" }: { kind?: "momentum" | "smart_money" }) {
  const [open, setOpen] = useState(false);

  const buckets = (
    <div className="flex items-center gap-1 text-[10px] tabular-nums">
      <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300">−1.0</span>
      <span className="text-zinc-700">·</span>
      <span className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-300/80">−0.5</span>
      <span className="text-zinc-700">·</span>
      <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500">0.0</span>
      <span className="text-zinc-700">·</span>
      <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300/80">+0.5</span>
      <span className="text-zinc-700">·</span>
      <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">+1.0</span>
    </div>
  );

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-zinc-500 mb-2">
      <span className="text-zinc-400">Score scale:</span>
      {buckets}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-zinc-500 hover:text-zinc-300 underline decoration-dotted underline-offset-2"
      >
        {open ? "less" : "what does this mean?"}
      </button>
      {open && (
        <div className="basis-full text-[11px] text-zinc-400 leading-relaxed pl-1 mt-1">
          {kind === "momentum" ? (
            <>
              Scores are cross-sectional within the asset class. Each symbol is
              ranked against its peers on recent return and RSI. <span className="text-emerald-300">≥+0.5</span>{" "}
              means the signal is in the top ~15% of the universe (strong long
              candidate). <span className="text-rose-300">≤−0.5</span> is bottom
              ~15% (strong short candidate). Values between ±0.2 are essentially
              noise — don't act on them.
            </>
          ) : (
            <>
              The smart-money score blends 13F breadth (how many tracked funds
              own this), insider net flow (buys − sells, 10b5-1 sales excluded),
              and Congress flow when available. <span className="text-emerald-300">≥+0.5</span>{" "}
              = high institutional conviction; <span className="text-rose-300">≤−0.5</span>{" "}
              = net selling. The 45-day disclosure lag eats most short-term alpha
              — treat as a confluence signal, not a real-time one.
            </>
          )}
        </div>
      )}
    </div>
  );
}
