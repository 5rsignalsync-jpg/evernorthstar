"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { PlaidLinkButton } from "@/components/PlaidLinkButton";
import {
  disconnectBrokerage,
  fetchPortfolio,
  syncBrokerage,
  type AnnotatedHolding,
  type BrokerageAccount,
  type PortfolioResponse,
} from "@/lib/api";

const QUALITY_COLORS: Record<string, string> = {
  strong: "text-emerald-300",
  mixed: "text-zinc-300",
  weak: "text-rose-300",
  unscored: "text-zinc-500",
};

function fmtUSD(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function fmtScore(s: number | null): string {
  if (s === null) return "—";
  return `${s >= 0 ? "+" : ""}${s.toFixed(3)}`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "never";
  try {
    return new Date(iso + "Z").toLocaleString();
  } catch {
    return iso;
  }
}

export default function PortfolioPage() {
  const { user, loading: authLoading, isPro } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetchPortfolio();
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/sign-in?next=/portfolio");
      return;
    }
    if (!isPro) return;  // render upsell instead of fetching
    void refresh();
  }, [user, authLoading, isPro, router, refresh]);

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
          <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-300 mb-6 inline-block">
            ← Back to dashboard
          </Link>
          <h1 className="text-2xl md:text-3xl font-semibold tracking-tight mb-2">
            Portfolio
          </h1>
          <p className="text-sm text-zinc-500 mb-6">
            Connect your brokerage to see your holdings cross-referenced against
            EverNorthstar signals + smart-money disclosures.
          </p>
          <div className="rounded-lg border border-indigo-500/40 bg-indigo-500/5 p-6">
            <h2 className="text-lg font-semibold text-zinc-100">Pro feature</h2>
            <p className="text-sm text-zinc-300 mt-2">
              Portfolio sync is included with Pro. Connect Fidelity, Schwab,
              Robinhood, and 10,000+ other brokerages. We never see your login
              credentials — Plaid handles authentication.
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

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6 md:p-10">
      <div className="max-w-5xl mx-auto">
        <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-300 mb-6 inline-block">
          ← Back to dashboard
        </Link>

        <div className="flex items-baseline justify-between flex-wrap gap-3 mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">
              Portfolio
            </h1>
            <p className="text-sm text-zinc-500 mt-1">
              Your holdings, cross-referenced against momentum signals + smart money.
            </p>
          </div>
          <PlaidLinkButton
            onLinked={() => void refresh()}
            label={data?.accounts.length ? "+ Add brokerage" : "+ Connect brokerage"}
          />
        </div>

        {error && (
          <p className="text-sm text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-3 py-2 mb-4">
            {error}
          </p>
        )}

        {loading && !data ? (
          <p className="text-sm text-zinc-500">Loading portfolio…</p>
        ) : data && data.accounts.length === 0 ? (
          <EmptyState plaidEnabled={data.plaid_enabled} />
        ) : data ? (
          <>
            <SummaryCards summary={data.summary} />
            <Accounts
              accounts={data.accounts}
              onChange={() => void refresh()}
            />
            <HoldingsTable holdings={data.holdings} />
          </>
        ) : null}
      </div>
    </main>
  );
}

function EmptyState({ plaidEnabled }: { plaidEnabled: boolean }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-8 text-center">
      <h2 className="text-lg font-semibold text-zinc-100">
        Connect your first brokerage
      </h2>
      <p className="text-sm text-zinc-400 mt-2 max-w-md mx-auto">
        Plaid handles the connection — we never see your username, password, or
        2FA codes. Holdings sync once daily.
      </p>
      <ul className="text-xs text-zinc-500 mt-4 space-y-1">
        <li>✓ 10,000+ supported institutions (Fidelity, Schwab, Robinhood, IBKR, etc)</li>
        <li>✓ Read-only — we can't trade on your behalf</li>
        <li>✓ Bank-grade encryption, SOC2 / SOC3 / ISO 27001 compliant via Plaid</li>
      </ul>
      {!plaidEnabled && (
        <p className="text-xs text-amber-400 mt-4 max-w-md mx-auto">
          Heads up: this deployment hasn't been provisioned with Plaid credentials yet.
          Clicking the button will show a friendly &quot;coming soon&quot; message until that's done.
        </p>
      )}
    </div>
  );
}

function SummaryCards({ summary }: { summary: PortfolioResponse["summary"] }) {
  const qualityColor =
    QUALITY_COLORS[summary.momentum_quality_label] ?? "text-zinc-400";
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <Card label="Total value" value={fmtUSD(summary.total_value_usd)} />
      <Card
        label="Positions"
        value={`${summary.n_holdings}`}
        sub={`${summary.n_with_signal} scored`}
      />
      <Card
        label="Momentum quality"
        value={summary.momentum_quality_label.toUpperCase()}
        sub={
          summary.weighted_momentum_score !== null
            ? `Weighted ${fmtScore(summary.weighted_momentum_score)}`
            : "no scored positions"
        }
        valueClass={qualityColor}
      />
      <Card
        label="Smart-money overlap"
        value={`${summary.smart_money_overlap_pct.toFixed(0)}%`}
        sub={`${summary.n_with_smart_money} positions tracked by funds`}
      />
    </div>
  );
}

function Card({
  label,
  value,
  sub,
  valueClass,
}: {
  label: string;
  value: string;
  sub?: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/40 p-3">
      <p className="text-[10px] text-zinc-500 uppercase tracking-wider">{label}</p>
      <p className={`text-lg font-semibold mt-1 ${valueClass ?? "text-zinc-100"}`}>
        {value}
      </p>
      {sub && <p className="text-[11px] text-zinc-500 mt-1">{sub}</p>}
    </div>
  );
}

function Accounts({
  accounts,
  onChange,
}: {
  accounts: BrokerageAccount[];
  onChange: () => void;
}) {
  async function onSync(id: number) {
    try {
      await syncBrokerage(id);
      onChange();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }
  async function onDisconnect(id: number, name: string) {
    if (!confirm(`Disconnect ${name}? This deletes the connection and all stored holdings.`)) return;
    try {
      await disconnectBrokerage(id);
      onChange();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/40 p-3 mb-6">
      <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">
        Connected accounts ({accounts.length})
      </p>
      <ul className="divide-y divide-zinc-800/60">
        {accounts.map((a) => (
          <li key={a.id} className="py-2 flex items-center justify-between gap-3 text-sm">
            <div className="min-w-0 flex-1">
              <p className="text-zinc-100 font-medium truncate">{a.institution_name}</p>
              <p className="text-[11px] text-zinc-500">
                {a.status === "active" ? "Active" : `Error: ${a.last_error ?? "unknown"}`}
                {" · "}Last sync: {fmtDate(a.last_synced_at)}
              </p>
            </div>
            <div className="shrink-0 flex items-center gap-2">
              <button
                onClick={() => void onSync(a.id)}
                className="text-[11px] text-zinc-400 hover:text-zinc-100 px-2 py-1 rounded border border-zinc-700"
              >
                Sync now
              </button>
              <button
                onClick={() => void onDisconnect(a.id, a.institution_name)}
                className="text-[11px] text-zinc-500 hover:text-rose-400"
              >
                Disconnect
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function HoldingsTable({ holdings }: { holdings: AnnotatedHolding[] }) {
  if (holdings.length === 0) {
    return (
      <p className="text-sm text-zinc-500 text-center py-8">
        No holdings yet. They'll appear here after the first sync (usually within
        a minute of connecting).
      </p>
    );
  }
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/40 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="text-[10px] uppercase tracking-wider text-zinc-500 bg-zinc-900/80">
          <tr>
            <th className="text-left px-3 py-2">Ticker</th>
            <th className="text-left px-3 py-2">Name</th>
            <th className="text-right px-3 py-2">Value</th>
            <th className="text-right px-3 py-2">Score</th>
            <th className="text-left px-3 py-2">Smart money</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h, i) => (
            <tr
              key={`${h.ticker ?? "x"}-${h.institution_name}-${i}`}
              className="border-t border-zinc-800/60"
            >
              <td className="px-3 py-2 font-medium text-zinc-100 tabular-nums">
                {h.ticker ?? <span className="text-zinc-600">—</span>}
              </td>
              <td className="px-3 py-2 text-zinc-300 max-w-[260px] truncate">
                {h.name}
                <span className="text-[10px] text-zinc-600 ml-2">
                  {h.institution_name}
                </span>
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-zinc-200">
                {fmtUSD(h.value)}
              </td>
              <td
                className={`px-3 py-2 text-right tabular-nums ${
                  h.momentum_score === null
                    ? "text-zinc-600"
                    : h.momentum_score > 0
                      ? "text-emerald-300"
                      : "text-rose-300"
                }`}
              >
                {fmtScore(h.momentum_score)}
              </td>
              <td className="px-3 py-2 text-xs text-zinc-400">
                {h.smart_money_actors.length > 0 ? (
                  <>
                    <span className="text-zinc-200">
                      {h.smart_money_actors.slice(0, 2).join(", ")}
                    </span>
                    {h.smart_money_actors.length > 2 && (
                      <span className="text-zinc-600"> +{h.smart_money_actors.length - 2}</span>
                    )}
                  </>
                ) : (
                  <span className="text-zinc-600">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
