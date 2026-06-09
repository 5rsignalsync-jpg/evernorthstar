/**
 * First-visit welcome overlay. localStorage flag dismisses it permanently
 * after the user clicks "Got it" or the close X. No multi-step pagination
 * — one screen with everything they need to feel oriented.
 */

"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "crypto-trends:onboarding-done:v1";

export function OnboardingTour() {
  // `null` = haven't checked storage yet (SSR-safe), `true`/`false` = decided.
  const [shouldShow, setShouldShow] = useState<boolean | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const done = window.localStorage.getItem(STORAGE_KEY);
    setShouldShow(done !== "1");
  }, []);

  const dismiss = () => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, "1");
    }
    setShouldShow(false);
  };

  if (!shouldShow) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
    >
      <div className="relative w-full max-w-lg rounded-lg border border-zinc-700 bg-zinc-950 p-6 shadow-2xl">
        <button
          onClick={dismiss}
          aria-label="Close welcome"
          className="absolute top-3 right-3 text-zinc-500 hover:text-zinc-100 text-xl leading-none"
        >
          ×
        </button>

        <h2 id="onboarding-title" className="text-xl font-semibold text-zinc-100 mb-2">
          Welcome to The<span className="text-emerald-400">Ever</span>Northstar 👋
        </h2>
        <p className="text-sm text-zinc-400 mb-4 leading-relaxed">
          Honest signals. Smart money. Always pointing north. ⭐{" "}
          Three things to know:
        </p>

        <ul className="space-y-2.5 text-sm text-zinc-300 mb-5">
          <li className="flex gap-2.5">
            <span className="text-emerald-400 mt-0.5">1.</span>
            <span>
              <strong className="text-zinc-100">Tabs are asset classes.</strong>{" "}
              Smart Money (where the famous-investor strategies live) is the
              default. Long-term holds, large caps, penny stocks, and crypto each
              have their own sleeve.
            </span>
          </li>
          <li className="flex gap-2.5">
            <span className="text-emerald-400 mt-0.5">2.</span>
            <span>
              <strong className="text-zinc-100">Click any row</strong> for a price
              chart, recent headlines (FinBERT-scored), and signal history.
            </span>
          </li>
          <li className="flex gap-2.5">
            <span className="text-emerald-400 mt-0.5">3.</span>
            <span>
              <strong className="text-zinc-100">⭐ to track.</strong> Starring a
              ticker adds it to your watchlist (stored locally — no account
              needed).
            </span>
          </li>
        </ul>

        <div className="rounded-md border border-amber-700/40 bg-amber-900/10 p-3 text-[11px] text-amber-200 mb-5 leading-relaxed">
          <strong>Honest reality check:</strong> there's a 2–45 day disclosure lag
          on smart-money data, walk-forward backtests show most retail-cost
          strategies barely beat zero, and we&apos;ll tell you when a signal isn&apos;t
          working. This is research, not advice.
        </div>

        <div className="flex justify-end gap-2">
          <button
            onClick={dismiss}
            className="px-4 py-2 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/30 text-sm font-medium"
          >
            Got it — show me the data
          </button>
        </div>
      </div>
    </div>
  );
}
