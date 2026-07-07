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
      <div className="w-full max-w-2xl text-center">
        <div className="text-5xl mb-4">🎉</div>
        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight mb-2">
          Welcome to <span className="text-emerald-400">Ever</span>Northstar Pro
        </h1>
        <p className="text-sm text-zinc-400 mb-6 leading-relaxed">
          Your subscription is active. The dashboard will unlock every Pro
          feature within a few seconds — we just need Stripe&apos;s
          confirmation to land.
        </p>

        <div className="rounded-md border border-emerald-500/30 bg-emerald-500/5 p-4 md:p-5 text-left text-sm mb-6">
          <p className="text-emerald-200 font-medium mb-3">
            What just unlocked
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-emerald-100/80 text-xs">
            <FeatureGroup title="Rankings + Smart Money">
              <li>Top 25 longs / shorts across every sleeve</li>
              <li>All 10 curated strategies with full baskets</li>
              <li>Unlimited watchlist</li>
              <li>CSV export of any sleeve</li>
              <li>Earnings calendar warnings</li>
            </FeatureGroup>

            <FeatureGroup title="AI features">
              <li>🤖 Ask Why — Claude explains any ticker&apos;s move</li>
              <li>📊 Earnings recap — Claude summarizes each report</li>
              <li>🤖 AI position summary on any plan</li>
              <li>📬 Optional daily digest email</li>
            </FeatureGroup>

            <FeatureGroup title="Portfolio + planning">
              <li>💼 Portfolio sync via Plaid (10,000+ institutions)</li>
              <li>🪙 Manual crypto positions with aggregation</li>
              <li>🎯 Position planner (extremum zones)</li>
              <li>🪜 Entry ladder (starter / core / deep rungs)</li>
              <li>💰 Cost-basis profit-taking framework (25/50/75%)</li>
              <li>📉 Historical outcomes at similar setups</li>
            </FeatureGroup>

            <FeatureGroup title="Alerts">
              <li>🚨 Unlimited email alerts</li>
              <li>Score / price thresholds</li>
              <li>Zone-target alerts (&quot;when BTC enters distribution&quot;)</li>
              <li>6-hour cooldown, no spam</li>
            </FeatureGroup>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-6">
          <Link
            href="/"
            className="block text-center py-2 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
          >
            Dashboard →
          </Link>
          <Link
            href="/planner"
            className="block text-center py-2 rounded-md bg-blue-500/20 border border-blue-500/40 text-blue-100 hover:bg-blue-500/30 text-sm font-medium"
          >
            Try the Planner
          </Link>
          <Link
            href="/portfolio"
            className="block text-center py-2 rounded-md bg-purple-500/20 border border-purple-500/40 text-purple-100 hover:bg-purple-500/30 text-sm font-medium"
          >
            Portfolio
          </Link>
        </div>

        <p className="text-[11px] text-zinc-500 leading-relaxed">
          Manage or cancel any time from your account page. 7-day refund
          window on first charge — just reply to your receipt email.
        </p>
      </div>
    </main>
  );
}

function FeatureGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-emerald-300/80 font-semibold mb-1.5">
        {title}
      </p>
      <ul className="space-y-1 list-none">{children}</ul>
    </div>
  );
}
