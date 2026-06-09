"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/** Same shape-handling as lib/auth.ts: FastAPI 422 returns `detail` as an array. */
function extractErr(body: unknown, status: number): string {
  if (!body || typeof body !== "object") return `${status}`;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e: { msg?: string; loc?: (string | number)[] }) => {
        const field = e.loc && e.loc.length > 0 ? String(e.loc[e.loc.length - 1]) : "field";
        return `${field}: ${e.msg ?? "invalid"}`;
      })
      .join("; ");
  }
  return `${status}`;
}

async function postCheckout(
  path: string,
  plan: "monthly" | "annual",
): Promise<string> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan }),
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      msg = extractErr(await res.json(), res.status);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  const data = await res.json();
  return data.url as string;
}

const startCheckout = (plan: "monthly" | "annual") =>
  postCheckout("/billing/checkout-session", plan);
const startCryptoCheckout = (plan: "monthly" | "annual") =>
  postCheckout("/billing/checkout-crypto", plan);

const FEATURES = {
  free: [
    "Crypto + Large Caps tabs",
    "Top 3 longs / 3 shorts per ranking",
    "Top 3 positions per strategy",
    "5 watchlist tickers",
    "Daily refresh (no real-time)",
    "Full price charts + headlines on drill-down",
    "Onboarding tour, score legends, all disclaimers",
  ],
  pro: [
    "All sleeves: Long-Term Picks, Penny Stocks, Smart Money",
    "Full top-25 rankings (longs + shorts)",
    "All 10 curated strategies + full position baskets",
    "Unlimited watchlist",
    "Real-time refresh + manual refresh button",
    "Earnings calendar warnings",
    "CSV export of any sleeve",
    "Email alerts (coming soon)",
  ],
};

export default function PricingPage() {
  const { user, isPro } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState<
    "monthly" | "annual" | "crypto-monthly" | "crypto-annual" | null
  >(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubscribe(plan: "monthly" | "annual") {
    setError(null);
    if (!user) {
      router.push(`/sign-up?next=/pricing`);
      return;
    }
    setLoading(plan);
    try {
      const url = await startCheckout(plan);
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setLoading(null);
    }
  }

  async function onSubscribeCrypto(plan: "monthly" | "annual") {
    setError(null);
    if (!user) {
      router.push(`/sign-up?next=/pricing`);
      return;
    }
    const key = (`crypto-${plan}`) as "crypto-monthly" | "crypto-annual";
    setLoading(key);
    try {
      const url = await startCryptoCheckout(plan);
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setLoading(null);
    }
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

        <h1 className="text-3xl font-semibold tracking-tight mb-2">
          The<span className="text-emerald-400">Ever</span>Northstar · Pricing
        </h1>
        <p className="text-sm text-zinc-400 mb-8">
          Honest pricing for an honest research tool. Cancel any time, refund
          within 7 days. Cards or crypto (BTC, ETH, SOL, XRP, XLM, HBAR + more).
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Free */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="text-xl font-semibold">Free</h2>
              <span className="text-zinc-400 text-sm">$0 / forever</span>
            </div>
            <p className="text-sm text-zinc-400 mb-4">
              A real working slice of the product — not a trial.
            </p>
            <ul className="space-y-1.5 text-sm text-zinc-300 mb-5">
              {FEATURES.free.map((f) => (
                <li key={f} className="flex gap-2">
                  <span className="text-zinc-500">·</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            {!user ? (
              <Link
                href="/sign-up"
                className="block w-full text-center py-2 rounded-md bg-zinc-800 border border-zinc-700 text-zinc-200 hover:bg-zinc-700 text-sm font-medium"
              >
                Create free account
              </Link>
            ) : isPro ? (
              <div className="text-center text-xs text-zinc-500 py-2">
                You&apos;re on Pro — Free is a no-op
              </div>
            ) : (
              <div className="text-center text-xs text-emerald-400 py-2">
                ✓ Your current plan
              </div>
            )}
          </div>

          {/* Pro */}
          <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-6 relative">
            <div className="absolute -top-2 right-4 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200">
              Recommended
            </div>
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="text-xl font-semibold">Pro</h2>
              <div className="text-right">
                <div className="text-zinc-200 text-base font-medium">
                  $19 <span className="text-zinc-500 text-sm">/ mo</span>
                </div>
                <div className="text-[11px] text-zinc-500">
                  or $190/yr · save 17%
                </div>
              </div>
            </div>
            <p className="text-sm text-zinc-300 mb-4">
              Everything in Free, plus the rest of the dashboard.
            </p>
            <ul className="space-y-1.5 text-sm text-zinc-200 mb-5">
              {FEATURES.pro.map((f) => (
                <li key={f} className="flex gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>

            {isPro ? (
              <div className="text-center text-xs text-emerald-300 py-2">
                ✓ Your current plan
              </div>
            ) : (
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => onSubscribe("monthly")}
                  disabled={loading !== null}
                  className="block w-full text-center py-2 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium disabled:opacity-50"
                >
                  {loading === "monthly"
                    ? "Redirecting to Stripe…"
                    : "Subscribe · $19 / month"}
                </button>
                <button
                  type="button"
                  onClick={() => onSubscribe("annual")}
                  disabled={loading !== null}
                  className="block w-full text-center py-2 rounded-md bg-zinc-800 border border-zinc-600 text-zinc-100 hover:bg-zinc-700 text-sm disabled:opacity-50"
                >
                  {loading === "annual"
                    ? "Redirecting to Stripe…"
                    : "Subscribe · $190 / year (save 17%)"}
                </button>
                <button
                  type="button"
                  onClick={() => onSubscribeCrypto("monthly")}
                  disabled={loading !== null}
                  className="block w-full text-center py-2 rounded-md bg-zinc-800 border border-zinc-700 text-zinc-200 hover:bg-zinc-700 text-xs disabled:opacity-50 mt-2"
                  title="Pay with BTC, ETH, SOL, XRP, XLM, HBAR, USDC, USDT, or 200+ more"
                >
                  {loading === "crypto-monthly"
                    ? "Redirecting to NOWPayments…"
                    : "Pay with crypto · monthly · BTC · ETH · SOL · XRP · XLM · HBAR"}
                </button>
                {error && (
                  <p className="text-[11px] text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-2 py-1.5 mt-2">
                    {error}
                  </p>
                )}
                {!user && (
                  <p className="text-[11px] text-zinc-500 text-center pt-2 leading-relaxed">
                    You&apos;ll need a free account first — clicking will take
                    you to sign-up and bring you back here.
                  </p>
                )}
                {user && (
                  <p className="text-[11px] text-zinc-500 text-center pt-2">
                    Hosted on Stripe. We never see your card number.
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Founder lifetime */}
        <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-5">
          <div className="flex items-baseline justify-between flex-wrap gap-2 mb-2">
            <h2 className="text-lg font-semibold text-amber-200">
              🎟️ Founder Lifetime · 100 spots
            </h2>
            <span className="text-amber-200 font-medium">
              $99 once · Pro forever
            </span>
          </div>
          <p className="text-sm text-amber-200/80 mb-3">
            Backs the build, locks in your Pro access permanently, and you get
            on a private Discord with direct input on the roadmap. Limited to
            the first 100 buyers.
          </p>
          <div className="inline-flex items-center gap-2">
            <div className="px-4 py-1.5 rounded-md bg-amber-500/15 border border-amber-500/30 text-amber-200/80 text-sm">
              Grab a spot
            </div>
            <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-amber-500/30 border border-amber-500/40 text-amber-100">
              Soon
            </span>
          </div>
        </div>

        <p className="text-xs text-zinc-500 mt-8 leading-relaxed">
          <strong className="text-zinc-400">Honest disclosures:</strong> we&apos;re
          a research dashboard, not a registered investment adviser. Backtests
          model realistic costs and we surface when signals don&apos;t work.
          Refunds within 7 days, no questions. Crypto payments are settled in
          USDC/USDT on our end — payment data is held by Stripe and NOWPayments,
          not us. Cancel any time from your account page.
        </p>
      </div>
    </main>
  );
}
