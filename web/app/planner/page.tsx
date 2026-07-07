"use client";

/**
 * Standalone Position Planner — the Merlin-style engine exposed for any
 * tracked ticker, no Plaid connection required.
 *
 * Users type a symbol (BTC, ETH, AAPL, etc.), optionally add quantity and
 * cost basis, and see the full PlanningCard: extremum zone, entry ladder,
 * ring-fence framework, historical outcome context, and (opt-in) Claude
 * summary. All Pro-gated.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { PlanningCard } from "@/components/PlanningCard";

type Query = {
  symbol: string;
  quantity?: number;
  costBasisPerShare?: number;
};

export default function PlannerPage() {
  const { user, loading: authLoading, isPro } = useAuth();
  const router = useRouter();

  // Form state (never triggers a plan fetch on its own)
  const [symbolInput, setSymbolInput] = useState("");
  const [quantityInput, setQuantityInput] = useState("");
  const [costInput, setCostInput] = useState("");

  // Committed query (drives the PlanningCard). Separate from form state so
  // the plan only refreshes when the user explicitly submits.
  const [query, setQuery] = useState<Query | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/sign-in?next=/planner");
    }
  }, [user, authLoading, router]);

  if (authLoading || !user) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center p-4">
        <p className="text-sm text-zinc-500">Loading…</p>
      </main>
    );
  }

  if (!isPro) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6 md:p-10">
        <div className="max-w-2xl mx-auto">
          <Link
            href="/"
            className="text-xs text-zinc-500 hover:text-zinc-300 mb-6 inline-block"
          >
            ← Back to dashboard
          </Link>
          <h1 className="text-2xl md:text-3xl font-semibold tracking-tight mb-2">
            Position Planner
          </h1>
          <p className="text-sm text-zinc-500 mb-6">
            Enter any tracked ticker and see its current zone, entry ladder,
            ring-fence-of-gains scenarios, and historical outcome context.
          </p>
          <div className="rounded-lg border border-indigo-500/40 bg-indigo-500/5 p-6">
            <h2 className="text-lg font-semibold text-zinc-100">Pro feature</h2>
            <p className="text-sm text-zinc-300 mt-2">
              The Position Planner is included with Pro. Free users see the
              rankings and public strategies; Pro unlocks the planning engine
              plus portfolio sync via Plaid, AI summaries, and unlimited
              alerts.
            </p>
            <Link
              href="/pricing"
              className="inline-block mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              See Pro plans →
            </Link>
          </div>
        </div>
      </main>
    );
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const sym = symbolInput.trim().toUpperCase();
    if (!sym) return;
    const q = quantityInput.trim() ? parseFloat(quantityInput) : undefined;
    const c = costInput.trim() ? parseFloat(costInput) : undefined;
    setQuery({
      symbol: sym,
      quantity: q && !Number.isNaN(q) ? q : undefined,
      costBasisPerShare: c && !Number.isNaN(c) ? c : undefined,
    });
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6 md:p-10">
      <div className="max-w-3xl mx-auto">
        <Link
          href="/"
          className="text-xs text-zinc-500 hover:text-zinc-300 mb-6 inline-block"
        >
          ← Back to dashboard
        </Link>

        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">
            🎯 Position Planner
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Enter a ticker to see its current zone, entry ladder, ring-fence
            framework, and historical outcome context. Optional quantity + cost
            basis power the profit-taking scenarios. Data-descriptive planning
            tool. Not investment advice.
          </p>
        </div>

        {/* Input form */}
        <form
          onSubmit={onSubmit}
          className="rounded-md border border-zinc-800 bg-zinc-900/40 p-4 mb-6 grid grid-cols-1 sm:grid-cols-4 gap-3 items-end"
        >
          <label className="block sm:col-span-2">
            <span className="text-[11px] text-zinc-400 uppercase tracking-wider">
              Ticker
            </span>
            <input
              type="text"
              value={symbolInput}
              onChange={(e) => setSymbolInput(e.target.value)}
              placeholder="BTC, ETH, AAPL, NVDA…"
              className="block w-full mt-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
              required
              autoFocus
            />
          </label>
          <label className="block">
            <span className="text-[11px] text-zinc-400 uppercase tracking-wider">
              Quantity <span className="text-zinc-600">(optional)</span>
            </span>
            <input
              type="number"
              step="any"
              value={quantityInput}
              onChange={(e) => setQuantityInput(e.target.value)}
              placeholder="0.5"
              className="block w-full mt-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
            />
          </label>
          <label className="block">
            <span className="text-[11px] text-zinc-400 uppercase tracking-wider">
              Cost / unit <span className="text-zinc-600">(optional)</span>
            </span>
            <input
              type="number"
              step="any"
              value={costInput}
              onChange={(e) => setCostInput(e.target.value)}
              placeholder="32000"
              className="block w-full mt-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
            />
          </label>
          <div className="sm:col-span-4 flex items-center gap-2 mt-1">
            <button
              type="submit"
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              Build plan
            </button>
            <p className="text-[11px] text-zinc-500">
              Skip quantity + cost basis for a market-only view. Include them
              for personalized ring-fence scenarios.
            </p>
          </div>
        </form>

        {/* Presets */}
        <div className="flex items-center flex-wrap gap-2 mb-6">
          <span className="text-[11px] text-zinc-500">Try:</span>
          {(["BTC", "ETH", "SOL", "AAPL", "NVDA", "TSLA"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setSymbolInput(s);
                setQuantityInput("");
                setCostInput("");
                setQuery({ symbol: s });
              }}
              className="text-[11px] rounded-md bg-zinc-800/60 border border-zinc-700 px-2.5 py-1 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100"
            >
              {s}
            </button>
          ))}
        </div>

        {/* Result */}
        {query ? (
          <PlanningCard
            key={`${query.symbol}-${query.quantity ?? ""}-${
              query.costBasisPerShare ?? ""
            }`}
            symbol={query.symbol}
            quantity={query.quantity}
            costBasisPerShare={query.costBasisPerShare}
          />
        ) : (
          <div className="rounded-md border border-dashed border-zinc-800 p-8 text-center">
            <p className="text-sm text-zinc-500">
              Enter a ticker above to build its plan.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
