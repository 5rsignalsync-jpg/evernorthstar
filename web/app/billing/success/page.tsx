"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";

export default function BillingSuccessPage() {
  const { refresh } = useAuth();

  useEffect(() => {
    // The Stripe webhook bumps tier server-side; refresh the user object so
    // the UI flips to Pro within ~1s.
    const interval = setInterval(() => refresh(), 1500);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md text-center">
        <div className="text-5xl mb-4">🎉</div>
        <h1 className="text-2xl font-semibold tracking-tight mb-2">
          Welcome to The<span className="text-emerald-400">Ever</span>Northstar Pro
        </h1>
        <p className="text-sm text-zinc-400 mb-6 leading-relaxed">
          Your subscription is active. The dashboard will unlock the rest of the
          sleeves, strategies, and watchlist capacity within a few seconds — we
          just need to receive Stripe&apos;s confirmation.
        </p>

        <div className="rounded-md border border-emerald-500/30 bg-emerald-500/5 p-4 text-left text-sm space-y-2 mb-6">
          <p className="text-emerald-200 font-medium">What just unlocked:</p>
          <ul className="text-emerald-100/80 text-xs space-y-1">
            <li>· Top 25 longs / 25 shorts on every sleeve</li>
            <li>· All 10 Smart Money strategies with full baskets</li>
            <li>· Unlimited watchlist</li>
            <li>· Earnings calendar warnings</li>
            <li>· CSV export of any sleeve</li>
            <li>· Email alerts (once we wire them this week)</li>
          </ul>
        </div>

        <Link
          href="/"
          className="block w-full text-center py-2 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
        >
          Go to dashboard →
        </Link>

        <p className="text-[11px] text-zinc-500 mt-6 leading-relaxed">
          Manage or cancel any time from your account page. 7-day refund window
          on first charge — just reply to your receipt email.
        </p>
      </div>
    </main>
  );
}
