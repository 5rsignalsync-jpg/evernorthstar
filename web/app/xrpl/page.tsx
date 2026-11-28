import type { Metadata } from "next";
import Link from "next/link";

// XRPL adoption tracker. Live metrics come from the backend's
// /xrpl/metrics endpoint (refreshed every 6h by the APScheduler job in
// crypto_trends.scheduler). ISR caches the server render for 30 min.
// Hard-coded constants below are the fallback for keys the backend
// doesn't currently populate (pipeline rows, gap analysis, YoY table,
// bank integration list) — those are editorial, not feed-driven.
// Lives at /xrpl AND via middleware at xrpl.evernorthstar.app.

export const revalidate = 1800; // 30 minutes

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type ApiMetric = {
  metric_key: string;
  value_text: string;
  value_numeric: number | null;
  sub_text: string | null;
  source: string | null;
  as_of_date: string | null;
  fetched_at: string;
};

type MetricsPayload = {
  metrics: Record<string, ApiMetric>;
  last_refresh: string | null;
};

async function fetchMetrics(): Promise<MetricsPayload> {
  try {
    const r = await fetch(`${API_BASE}/xrpl/metrics`, {
      next: { revalidate: 1800 },
    });
    if (!r.ok) {
      return { metrics: {}, last_refresh: null };
    }
    return (await r.json()) as MetricsPayload;
  } catch {
    // Backend down, DNS hiccup, cold start timeout — fall back silently.
    return { metrics: {}, last_refresh: null };
  }
}

export const metadata: Metadata = {
  title: "XRPL Adoption Tracker — The Honest Snapshot | EverNorthstar",
  description:
    "Real XRP Ledger adoption data: tokenized RWA value, RLUSD growth, spot XRP ETF flows, named bank integrations, protocol roadmap, and honest gap analysis for each price target. Updated regularly. Every number cited.",
  openGraph: {
    title: "XRPL Adoption Tracker — The Honest Snapshot",
    description:
      "Where XRPL actually is vs. where it's going. Objective adoption data for the XRP Ledger. No hype, no sentiment scoring, every number sourced.",
    url: "https://xrpl.evernorthstar.app",
    siteName: "EverNorthstar",
    type: "website",
  },
  alternates: {
    canonical: "https://xrpl.evernorthstar.app",
  },
};

// NOW_METRICS fallback. apiKey is the metric_key from the backend —
// when the API returns that key, we overlay its value/sub/source onto
// this row. Rows without an apiKey are editorial (hand-curated).
const NOW_METRICS: Array<{
  apiKey?: string;
  label: string;
  value: string;
  sub?: string;
  source: string;
}> = [
  {
    apiKey: "rwa_total_usd",
    label: "Tokenized RWA value on XRPL",
    value: "~$3.6B",
    sub: "On-chain measure (rwa.xyz). ~50% in a single Justoken JMWH energy token — concentration risk is real.",
    source: "rwa.xyz · as of 2026-11-27",
  },
  {
    apiKey: "rlusd_supply_usd",
    label: "RLUSD circulating supply",
    value: "$2.87B",
    sub: "From $0 at Dec 2024 launch",
    source: "CoinGecko · as of 2026-11-22",
  },
  {
    apiKey: "xrp_etf_net_assets_usd",
    label: "US spot XRP ETF net assets",
    value: "$1.15B",
    sub: "Cumulative inflows $1.79B · week of Nov 9-13 saw -$19.1M outflow (largest in 8 months)",
    source: "SoSoValue · as of 2026-11-13",
  },
  {
    label: "Named production bank integrations",
    value: "16+",
    sub: "BNY Mellon, Standard Chartered, Cross River, SBI, HSBC, Kyobo, Meritz, Jeonbuk, Yapı Kredi (Türkiye, Nov 25 2026), Deutsche Bank (announced), Robinhood (institutional), +",
    source: "Ripple press releases 2026",
  },
  {
    label: "Moody's-rated stablecoins on XRPL",
    value: "1",
    sub: "RLUSD A2 / P-1 — first investment-grade stablecoin ever",
    source: "Moody's, Oct 28 2026",
  },
  {
    label: "Ripple regulated banking entity",
    value: "Live",
    sub: "Ripple National Trust Bank (OCC approved)",
    source: "OCC, Oct 2026",
  },
];

const PROTOCOL_STATUS: Array<{
  apiKey?: string;
  item: string;
  status: string;
  detail: string;
}> = [
  {
    apiKey: "xls_65_status",
    item: "XLS-65 SingleAssetVault",
    status: "PASSED — activates Dec 9 2026",
    detail: "Lending collateral primitive. Validator majority reached Nov 25 2026; 14-day activation hold in progress.",
  },
  {
    apiKey: "xls_66_status",
    item: "XLS-66 LendingProtocol",
    status: "PASSED — activates Dec 11 2026",
    detail: "Native XRPL lending (29/35 validator votes). Majority reached Nov 27 2026; 14-day activation hold in progress.",
  },
  {
    item: "XRPL V1_1 patch",
    status: "In voting (denominator /35)",
    detail: "Protocol patch. XRPL default UNL migrated to ~35 validators in late 2025, so vote counts now use /35, not /28.",
  },
  {
    item: "Permissioned DEX",
    status: "Live (Q2 2026 delivered)",
    detail: "Conversion layer for Ripple Payments.",
  },
  {
    item: "Confidential Transfers (MPT)",
    status: "Roadmap",
    detail: "Multi-Purpose Token privacy layer.",
  },
  {
    item: "Smart Escrows",
    status: "Roadmap",
    detail: "Programmable escrow conditions.",
  },
];

const PIPELINE: Array<{
  who: string;
  what: string;
  status: "Announced" | "Pilot" | "Testnet" | "Mainnet (ramping)";
  eta: string;
  source: string;
}> = [
  {
    who: "BNY Mellon + Ripple",
    what: "Tokenized trade finance on XRPL (exploratory pilot)",
    status: "Announced",
    eta: "2027",
    source: "Ripple Swell 2026 Day 0",
  },
  {
    who: "Aviva Investors",
    what: "Tokenized traditional fund structures on XRPL",
    status: "Pilot",
    eta: "2026-2027 ongoing",
    source: "Ripple + Aviva joint announcement 2026",
  },
  {
    who: "Mastercard + JPMorgan Kinexys + Ondo + Ripple",
    what: "Cross-border tokenized Treasury settlement via XRPL",
    status: "Pilot",
    eta: "Completed May 2026; expanding",
    source: "Joint release, May 2026",
  },
  {
    who: "Robinhood",
    what: "RLUSD on XRPL for institutional settlement + Ripple Treasury integration",
    status: "Announced",
    eta: "2027 integration",
    source: "Ripple Swell 2026 Day 0",
  },
  {
    who: "Cross River Bank",
    what: "RLUSD on XRPL integrated into core banking platform",
    status: "Mainnet (ramping)",
    eta: "Q1 2027",
    source: "Ripple, Oct 2026",
  },
  {
    who: "Clearpool",
    what: "RLUSD lending flow on XRPL mainnet",
    status: "Testnet",
    eta: "Pending XLS-65/66 activation",
    source: "Clearpool demo, Nov 19 2026",
  },
  {
    who: "Kyobo Life Insurance (Korea)",
    what: "Tokenized Korean government bond settlement via Ripple Custody",
    status: "Pilot",
    eta: "Expanding 2027",
    source: "Ripple + Kyobo, April 2026",
  },
  {
    who: "Meritz Securities (Korea)",
    what: "Ripple integration — product scope to be announced",
    status: "Announced",
    eta: "TBD",
    source: "Ripple, Oct 14 2026",
  },
  {
    who: "Deutsche Bank",
    what: "Ripple infrastructure use (announced intention)",
    status: "Announced",
    eta: "Unconfirmed",
    source: "Secondary sources, Feb 2026",
  },
  {
    who: "XRPN (Evernorth Holdings)",
    what: "Nasdaq-listed XRP treasury vehicle (473M XRP)",
    status: "Mainnet (ramping)",
    eta: "Approved Sept 30 2026; closing conditions in-flight",
    source: "Armada Acquisition Corp. II shareholder vote",
  },
  {
    who: "Ripple Prime (Hidden Road)",
    what: "Migrate $3T/yr post-trade clearing activity to XRPL + RLUSD collateral",
    status: "Pilot",
    eta: "2027 ramp",
    source: "Ripple, 2026",
  },
  {
    who: "Central Banks — CBDC Platform",
    what: "Active engagements (Bhutan, Palau, Hong Kong, Colombia, Montenegro, Georgia)",
    status: "Pilot",
    eta: "Rolling",
    source: "IMF + Ripple public disclosures",
  },
];

const GAP_TARGETS: Array<{
  price: string;
  marketCap: string;
  required: string[];
  status: "Partially met" | "Pipeline" | "Aspirational" | "Hyper-bull";
  statusColor: string;
}> = [
  {
    price: "$5 XRP",
    marketCap: "~$275B",
    required: [
      "Current ETF inflows sustain (reverse November outflow trend)",
      "2-3 new named bank integrations in production (vs. announced)",
      "XRPL lending (XLS-65/66) activates on mainnet",
      "BNY Mellon institutional XRP accumulation operationalizes",
      "RLUSD circulation grows to $5B+",
    ],
    status: "Partially met",
    statusColor: "text-amber-300 border-amber-500/40 bg-amber-500/5",
  },
  {
    price: "$20 XRP",
    marketCap: "~$1.1T",
    required: [
      "Combined XRP ETF AUM reaches $25B+",
      "10+ named institutional integrations live in production (not just announced)",
      "RLUSD circulation hits $25B+",
      "At least 1 CBDC pilot moves to production",
      "Ripple Prime routes meaningful % of $3T clearing volume through XRPL",
      "XRPL tokenized RWA value crosses $50B",
    ],
    status: "Pipeline",
    statusColor: "text-blue-300 border-blue-500/40 bg-blue-500/5",
  },
  {
    price: "$50 XRP",
    marketCap: "~$2.75T",
    required: [
      "Combined XRP ETF AUM $50B+ (comparable to BTC ETF scale)",
      "XRP becomes direct settlement asset for 1+ central bank reserve",
      "XRPL established as dominant RWA tokenization chain (vs. Stellar, Ethereum, Canton)",
      "$500B+ tokenized assets settled on XRPL annually",
      "XRP liquidity depth supports $1B+ institutional transactions without slippage",
      "Regulatory framework (US + EU) stable and XRP-favorable",
    ],
    status: "Aspirational",
    statusColor: "text-purple-300 border-purple-500/40 bg-purple-500/5",
  },
  {
    price: "$100 XRP",
    marketCap: "~$5.5T",
    required: [
      "XRP replaces SWIFT corridors at measurable scale",
      "3+ central banks hold XRP as strategic reserve asset",
      "$1T+ tokenized assets on XRPL",
      "Full integration of Ripple's enterprise stack (Prime + Custody + Trust Bank + CBDC) at scale",
      "XRP market cap eclipses ETH into #2 by crypto market cap",
      "Macro environment: Fed cutting cycle + crypto late-cycle parabolic",
    ],
    status: "Hyper-bull",
    statusColor: "text-rose-300 border-rose-500/40 bg-rose-500/5",
  },
];

const YOY_COMPARISON: Array<{
  metric: string;
  nov2025: string;
  nov2026: string;
  change: string;
}> = [
  {
    metric: "Tokenized RWA value on XRPL",
    nov2025: "$364M (Messari Q3) / $394M",
    nov2026: "~$3.6B (rwa.xyz on-chain)",
    change: "+9× to +10×",
  },
  {
    metric: "RLUSD circulating supply",
    nov2025: "$0 (launched Dec 2024, just beginning)",
    nov2026: "$2.87B",
    change: "from zero",
  },
  {
    metric: "US spot XRP ETF AUM",
    nov2025: "$336M (Canary XRPC alone)",
    nov2026: "$1.15B (all issuers)",
    change: "+3.4×",
  },
  {
    metric: "ETF cumulative inflows",
    nov2025: "~$336M",
    nov2026: "$1.79B",
    change: "+5.3×",
  },
  {
    metric: "Moody's IG-rated stablecoins on XRPL",
    nov2025: "0",
    nov2026: "1 (RLUSD A2/P-1)",
    change: "first ever",
  },
  {
    metric: "Named production bank integrations",
    nov2025: "~2-3 verified",
    nov2026: "16+",
    change: "+5-8×",
  },
  {
    metric: "Federally regulated Ripple banking entity",
    nov2025: "None",
    nov2026: "Ripple National Trust Bank (OCC)",
    change: "new",
  },
  {
    metric: "Native XRPL lending",
    nov2025: "Experimental / off-ledger",
    nov2026: "XLS-65 passed Nov 25 (activates Dec 9) · XLS-66 passed Nov 27 (activates Dec 11)",
    change: "new primitive",
  },
  {
    metric: "XRP price YTD",
    nov2025: "—",
    nov2026: "−29% YTD 2026",
    change: "divergence",
  },
];

function Metric({
  label,
  value,
  sub,
  source,
}: {
  label: string;
  value: string;
  sub?: string;
  source: string;
}) {
  return (
    <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
      <p className="text-[10px] uppercase tracking-widest text-emerald-400 mb-1">
        {label}
      </p>
      <p className="text-2xl md:text-3xl font-semibold text-emerald-100 tabular-nums">
        {value}
      </p>
      {sub && (
        <p className="text-[11px] text-zinc-300 mt-1.5 leading-snug">{sub}</p>
      )}
      <p className="text-[10px] text-zinc-500 mt-2 italic">src: {source}</p>
    </div>
  );
}

function overlayMetric<T extends { apiKey?: string; value: string; sub?: string; source: string }>(
  base: T,
  api: Record<string, ApiMetric>,
): T {
  if (!base.apiKey) return base;
  const live = api[base.apiKey];
  if (!live) return base;
  const asOf = live.as_of_date ? new Date(live.as_of_date).toISOString().slice(0, 10) : null;
  return {
    ...base,
    value: live.value_text || base.value,
    sub: live.sub_text ?? base.sub,
    source: live.source
      ? asOf ? `${live.source} · as of ${asOf}` : live.source
      : base.source,
  };
}

function overlayProtocol<T extends { apiKey?: string; status: string; detail: string }>(
  base: T,
  api: Record<string, ApiMetric>,
): T {
  if (!base.apiKey) return base;
  const live = api[base.apiKey];
  if (!live) return base;
  return {
    ...base,
    status: live.value_text || base.status,
    detail: live.sub_text ?? base.detail,
  };
}

function formatLastRefresh(iso: string | null): string {
  if (!iso) return "Data as of: Nov 27 2026 · refresh pending";
  const d = new Date(iso);
  const date = d.toLocaleDateString(undefined, {
    year: "numeric", month: "short", day: "numeric",
  });
  const time = d.toLocaleTimeString(undefined, {
    hour: "2-digit", minute: "2-digit", timeZoneName: "short",
  });
  return `Last auto-refresh: ${date} ${time}`;
}

export default async function XrplTrackerPage() {
  const { metrics, last_refresh } = await fetchMetrics();
  const liveNowMetrics = NOW_METRICS.map((m) => overlayMetric(m, metrics));
  const liveProtocol = PROTOCOL_STATUS.map((p) => overlayProtocol(p, metrics));

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-16 pb-10">
        <p className="text-xs uppercase tracking-widest text-emerald-400 mb-3">
          XRPL Adoption Tracker · The honest snapshot
        </p>
        <h1 className="text-3xl md:text-5xl font-semibold tracking-tight mb-4">
          Where XRPL actually is — and what has to happen next
        </h1>
        <p className="text-lg md:text-xl text-zinc-300 leading-relaxed mb-6 max-w-3xl">
          Objective adoption data for the XRP Ledger. No opinion-based scoring.
          No sentiment inflation. Every number is sourced. Updated regularly
          with hand-curated institutional integrations and pipeline items.
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <a
            href="#now"
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
          >
            Current snapshot ↓
          </a>
          <a
            href="#gap"
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-md bg-zinc-800 border border-zinc-700 text-zinc-100 hover:bg-zinc-700 text-sm font-medium"
          >
            What it takes to reach $20 / $50 / $100 XRP
          </a>
        </div>
      </section>

      {/* NOW — live snapshot */}
      <section id="now" className="max-w-5xl mx-auto px-6 pb-10">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-2xl font-semibold tracking-tight">
            NOW — Current adoption snapshot
          </h2>
          <p className="text-xs text-zinc-500">
            {formatLastRefresh(last_refresh)}
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {liveNowMetrics.map((m) => (
            <Metric key={m.label} {...m} />
          ))}
        </div>
      </section>

      {/* Year-over-year */}
      <section className="max-w-5xl mx-auto px-6 pb-10">
        <h2 className="text-2xl font-semibold tracking-tight mb-4">
          Year-over-year — Nov 2025 → Nov 2026
        </h2>
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900/60 text-[10px] uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="text-left py-2 px-3 font-normal">Metric</th>
                <th className="text-left py-2 px-3 font-normal">Nov 2025</th>
                <th className="text-left py-2 px-3 font-normal">Nov 2026</th>
                <th className="text-right py-2 px-3 font-normal">Change</th>
              </tr>
            </thead>
            <tbody>
              {YOY_COMPARISON.map((r) => (
                <tr key={r.metric} className="border-t border-zinc-800/60 align-top">
                  <td className="py-3 px-3 text-zinc-200 font-medium">{r.metric}</td>
                  <td className="py-3 px-3 text-zinc-400 text-[13px]">{r.nov2025}</td>
                  <td className="py-3 px-3 text-emerald-200 text-[13px]">{r.nov2026}</td>
                  <td className="py-3 px-3 text-right text-emerald-300 font-semibold tabular-nums">
                    {r.change}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Protocol status */}
      <section className="max-w-5xl mx-auto px-6 pb-10">
        <h2 className="text-2xl font-semibold tracking-tight mb-4">
          Protocol status — amendments + roadmap
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {liveProtocol.map((p) => (
            <div
              key={p.item}
              className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4"
            >
              <p className="text-sm font-semibold text-zinc-100">{p.item}</p>
              <p className="text-xs text-emerald-300 mt-1">{p.status}</p>
              <p className="text-[12px] text-zinc-400 mt-2 leading-snug">
                {p.detail}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="max-w-5xl mx-auto px-6 pb-10">
        <h2 className="text-2xl font-semibold tracking-tight mb-1">
          PIPELINE — announced but not fully live
        </h2>
        <p className="text-sm text-zinc-500 mb-4">
          Every row is a named integration or product. Status reflects the
          latest public disclosure.
        </p>
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900/60 text-[10px] uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="text-left py-2 px-3 font-normal">Who</th>
                <th className="text-left py-2 px-3 font-normal">What</th>
                <th className="text-left py-2 px-3 font-normal">Status</th>
                <th className="text-left py-2 px-3 font-normal">ETA</th>
                <th className="text-left py-2 px-3 font-normal">Source</th>
              </tr>
            </thead>
            <tbody>
              {PIPELINE.map((p) => (
                <tr key={p.who + p.what} className="border-t border-zinc-800/60 align-top">
                  <td className="py-3 px-3 text-zinc-100 font-medium whitespace-nowrap">
                    {p.who}
                  </td>
                  <td className="py-3 px-3 text-zinc-300">{p.what}</td>
                  <td className="py-3 px-3 whitespace-nowrap">
                    <span
                      className={
                        "inline-block text-[11px] px-2 py-0.5 rounded " +
                        (p.status === "Mainnet (ramping)"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                          : p.status === "Pilot"
                            ? "bg-blue-500/20 text-blue-300 border border-blue-500/40"
                            : p.status === "Testnet"
                              ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
                              : "bg-amber-500/20 text-amber-300 border border-amber-500/40")
                      }
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-zinc-400 text-[12px] whitespace-nowrap">
                    {p.eta}
                  </td>
                  <td className="py-3 px-3 text-zinc-500 text-[11px]">{p.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* TO-GET-THERE — gap analysis */}
      <section id="gap" className="max-w-5xl mx-auto px-6 pb-10">
        <h2 className="text-2xl font-semibold tracking-tight mb-1">
          TO-GET-THERE — what has to happen for each XRP price target
        </h2>
        <p className="text-sm text-zinc-500 mb-4">
          Honest, data-grounded checklist. Not a prediction — a gap analysis.
        </p>
        <div className="space-y-4">
          {GAP_TARGETS.map((t) => (
            <div
              key={t.price}
              className={"rounded-lg border p-5 " + t.statusColor}
            >
              <div className="flex items-baseline justify-between mb-3">
                <h3 className="text-xl font-semibold tracking-tight">
                  {t.price}
                </h3>
                <div className="text-right">
                  <p className="text-[11px] uppercase tracking-wider opacity-70">
                    Market cap
                  </p>
                  <p className="text-sm tabular-nums">{t.marketCap}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-[11px] uppercase tracking-wider opacity-70">
                  Status:
                </span>
                <span className="text-sm font-semibold">{t.status}</span>
              </div>
              <ul className="space-y-1.5 text-sm">
                {t.required.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="opacity-60">•</span>
                    <span className="text-zinc-200">{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Email capture */}
      <section className="max-w-3xl mx-auto px-6 pb-10">
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-6 text-center">
          <h2 className="text-xl font-semibold tracking-tight mb-2">
            Get the weekly XRPL adoption update
          </h2>
          <p className="text-sm text-zinc-400 mb-5 leading-relaxed max-w-lg mx-auto">
            Honest data every Monday: new integrations, amendment votes, ETF
            flows, pipeline changes. No hype, no sentiment scoring. One email
            per week.
          </p>
          <Link
            href="/sign-up?utm_source=xrpl-tracker"
            className="inline-flex items-center justify-center px-6 py-3 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
          >
            Sign up free → get the digest
          </Link>
          <p className="text-[11px] text-zinc-600 mt-3">
            Also unlocks EverNorthstar&apos;s full dashboard — rankings, zones,
            Smart Money data, position planner.
          </p>
        </div>
      </section>

      {/* Methodology + sources */}
      <section className="max-w-5xl mx-auto px-6 pb-16 text-[12px] text-zinc-500">
        <h3 className="text-sm uppercase tracking-wider text-zinc-400 mb-3">
          Methodology + sources
        </h3>
        <div className="space-y-3 leading-relaxed">
          <p>
            <strong className="text-zinc-300">Objective data only.</strong> No
            sentiment scoring, no X-mentions weighting, no "momentum" factors.
            Every number here is from a primary public source (Ripple press
            releases, SEC filings, Moody&apos;s, OCC, CoinGecko, SoSoValue,
            DeFiLlama, XRPSCAN, company earnings reports).
          </p>
          <p>
            <strong className="text-zinc-300">Partial automation.</strong>{" "}
            Core metrics (RLUSD supply via CoinGecko, XRP ETF via SoSoValue,
            tokenized RWA via rwa.xyz, XRPL amendment status) auto-refresh
            every 6 hours from the EverNorthstar backend. Editorial sections
            (pipeline, bank integrations, gap analysis) are hand-curated —
            auto-pipelines for those are coming.
          </p>
          <p>
            <strong className="text-zinc-300">Named integrations</strong> are
            included only when announced by Ripple, the partner institution,
            or verified by a reputable outlet (CoinDesk, Reuters, Bloomberg,
            CoinTelegraph, The Block). Marketing-only press releases without
            product specifics are excluded.
          </p>
          <p>
            <strong className="text-zinc-300">
              "To-get-there" gap analysis
            </strong>{" "}
            is an opinion-informed checklist built from historical
            price/market-cap/adoption relationships. Not a prediction. Not
            financial advice.
          </p>
          <p className="pt-3 text-[11px] text-zinc-600">
            Published by EverNorthstar, a product of 5 Royals Investments
            Digital (Wyoming) and its Texas operating entity. EverNorthstar is
            a research publisher under the Lowe v. SEC publisher exemption. We
            are NOT a registered investment adviser or broker-dealer.
          </p>
        </div>
      </section>
    </main>
  );
}
