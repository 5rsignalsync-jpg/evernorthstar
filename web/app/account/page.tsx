"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AdminPanel } from "@/components/AdminPanel";
import { AlertsSection } from "@/components/AlertsSection";
import { useAuth } from "@/components/AuthProvider";
import { openBillingPortal, updatePrefs } from "@/lib/auth";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso + "Z").toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function AccountPage() {
  const { user, loading, logout, isPro, refresh } = useAuth();
  const router = useRouter();
  const [portalLoading, setPortalLoading] = useState(false);
  const [portalError, setPortalError] = useState<string | null>(null);
  const [digestSaving, setDigestSaving] = useState(false);
  const [digestError, setDigestError] = useState<string | null>(null);

  async function onToggleDigest(next: boolean) {
    setDigestError(null);
    setDigestSaving(true);
    try {
      await updatePrefs({ daily_digest_opt_in: next });
      await refresh();
    } catch (e) {
      setDigestError(e instanceof Error ? e.message : String(e));
    } finally {
      setDigestSaving(false);
    }
  }

  // Redirect to sign-in if not authenticated.
  useEffect(() => {
    if (!loading && !user) router.push("/sign-in?next=/account");
  }, [loading, user, router]);

  async function onManageBilling() {
    setPortalError(null);
    setPortalLoading(true);
    try {
      const url = await openBillingPortal();
      window.location.href = url;
    } catch (e) {
      setPortalError(e instanceof Error ? e.message : String(e));
      setPortalLoading(false);
    }
  }

  if (loading || !user) {
    return (
      <main className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center p-4">
        <p className="text-sm text-zinc-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6 md:p-10">
      <div className="max-w-2xl mx-auto">
        <Link
          href="/"
          className="text-xs text-zinc-500 hover:text-zinc-300 mb-6 inline-block"
        >
          ← Back to dashboard
        </Link>

        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight mb-1">
          Account
        </h1>
        <p className="text-sm text-zinc-500 mb-8">
          Manage your subscription, payment method, and view receipts.
        </p>

        {/* Profile */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5 mb-4">
          <h2 className="text-sm uppercase tracking-wider text-zinc-500 mb-3">
            Profile
          </h2>
          <dl className="text-sm space-y-2">
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-400">Email</dt>
              <dd className="text-zinc-100 font-medium break-all text-right">
                {user.email}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-400">Account ID</dt>
              <dd className="text-zinc-500 tabular-nums">#{user.id}</dd>
            </div>
          </dl>
        </div>

        {/* Subscription */}
        <div
          className={
            "rounded-lg border p-5 mb-4 " +
            (isPro
              ? "border-emerald-500/40 bg-emerald-500/5"
              : "border-zinc-800 bg-zinc-900/60")
          }
        >
          <h2 className="text-sm uppercase tracking-wider text-zinc-500 mb-3">
            Subscription
          </h2>
          <dl className="text-sm space-y-2 mb-4">
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-400">Plan</dt>
              <dd>
                {isPro ? (
                  <span className="px-2 py-0.5 text-xs rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 uppercase tracking-wider">
                    Pro
                  </span>
                ) : (
                  <span className="px-2 py-0.5 text-xs rounded border border-zinc-700 bg-zinc-800 text-zinc-400 uppercase tracking-wider">
                    Free
                  </span>
                )}
              </dd>
            </div>
            {user.subscription_expires_at && (
              <div className="flex justify-between gap-3">
                <dt className="text-zinc-400">
                  {isPro ? "Renews / expires" : "Expired"}
                </dt>
                <dd className="text-zinc-100">
                  {formatDate(user.subscription_expires_at)}
                </dd>
              </div>
            )}
          </dl>

          {isPro ? (
            <div className="space-y-2">
              <button
                type="button"
                onClick={onManageBilling}
                disabled={portalLoading}
                className="block w-full text-center py-2 rounded-md bg-zinc-800 border border-zinc-600 text-zinc-100 hover:bg-zinc-700 text-sm disabled:opacity-50"
              >
                {portalLoading
                  ? "Redirecting to Stripe…"
                  : "Manage subscription · Stripe portal"}
              </button>
              <p className="text-[11px] text-zinc-500">
                Update card, view invoices, or cancel your subscription on the
                Stripe-hosted portal. Cancellations take effect at the end of
                your current billing period — no surprise lockouts.
              </p>
            </div>
          ) : (
            <Link
              href="/pricing"
              className="block w-full text-center py-2 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
            >
              Upgrade to Pro · $19/mo or $190/yr
            </Link>
          )}

          {portalError && (
            <p className="text-[11px] text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-2 py-1.5 mt-3">
              {portalError}
            </p>
          )}
        </div>

        {/* Admin (visible only to admins) */}
        {user.is_admin && <AdminPanel />}

        {/* Alerts */}
        <AlertsSection isPro={isPro} />

        {/* Email preferences */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5 mb-4">
          <h2 className="text-sm uppercase tracking-wider text-zinc-500 mb-3">
            Email preferences
          </h2>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm text-zinc-200 font-medium">
                Daily AI digest
              </p>
              <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
                A 5-bullet morning summary of overnight movers, smart-money
                disclosures, and notable headlines — written by Claude from
                EverNorthstar's signals. Sent ~7am ET. Unsubscribe anytime.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={user.daily_digest_opt_in}
              disabled={digestSaving}
              onClick={() => onToggleDigest(!user.daily_digest_opt_in)}
              className={
                "shrink-0 inline-flex items-center h-6 w-11 rounded-full transition " +
                (user.daily_digest_opt_in
                  ? "bg-emerald-500/70"
                  : "bg-zinc-700") +
                (digestSaving ? " opacity-50 cursor-wait" : " cursor-pointer")
              }
            >
              <span
                className={
                  "h-5 w-5 rounded-full bg-white shadow transition-transform " +
                  (user.daily_digest_opt_in ? "translate-x-5" : "translate-x-0.5")
                }
              />
            </button>
          </div>
          {digestError && (
            <p className="text-[11px] text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-2 py-1.5 mt-3">
              {digestError}
            </p>
          )}
        </div>

        {/* Sign out */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
          <h2 className="text-sm uppercase tracking-wider text-zinc-500 mb-3">
            Session
          </h2>
          <button
            type="button"
            onClick={async () => {
              await logout();
              router.push("/");
            }}
            className="block w-full text-center py-2 rounded-md bg-rose-900/30 border border-rose-700/40 text-rose-200 hover:bg-rose-900/50 text-sm"
          >
            Sign out
          </button>
        </div>

        <p className="text-[11px] text-zinc-600 mt-6 leading-relaxed">
          Need help? Reply to your receipt email or reach out via support. 7-day
          refund window on the first charge — no questions asked.
        </p>
      </div>
    </main>
  );
}
