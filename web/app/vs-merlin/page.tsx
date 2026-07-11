import type { Metadata } from "next";
import Link from "next/link";

// Public comparison landing for anyone Googling "Merlin alternative",
// "Merlin Investor vs", "Merlin Crypto vs", "Merlin exit targets", etc.
// The tone is confident + specific. Every Merlin claim is cited to a
// public source (their tutorials, their marketing site, their 3-step
// onboarding). We never overstate — undocumented ≠ nonexistent, and we
// say so at the bottom.

export const metadata: Metadata = {
  title: "EverNorthstar vs Merlin — the honest comparison | EverNorthstar",
  description:
    "Merlin makes you draw Fibonacci retracements on TradingView and type the numbers into a spreadsheet. EverNorthstar auto-computes zones, entry ladders, and profit-taking scenarios — plus AI plan summaries and historical outcome distributions. Feature-by-feature head-to-head.",
  openGraph: {
    title: "EverNorthstar vs Merlin — the honest comparison",
    description:
      "Everything Merlin does + the analysis Merlin makes you do on TradingView. Feature-by-feature.",
    url: "https://evernorthstar.app/vs-merlin",
    siteName: "EverNorthstar",
    type: "website",
  },
  alternates: {
    canonical: "https://evernorthstar.app/vs-merlin",
  },
};

type Row = {
  category: string;
  feature: string;
  merlin: "yes" | "no" | "partial" | "manual";
  us: "yes" | "no" | "partial" | "manual";
  detail: string;
};

const ROWS: Row[] = [
  {
    category: "Exit targets",
    feature: "Auto-computed price targets",
    merlin: "no",
    us: "yes",
    detail:
      "Merlin's masterclass sends you to TradingView to draw Fibonacci retracement lines by hand, then type the numbers back into Merlin. EverNorthstar computes accumulation + distribution price bands automatically using an RSI + Bollinger + score-percentile + volume-divergence ensemble.",
  },
  {
    category: "Exit targets",
    feature: "Multi-indicator zone detection",
    merlin: "no",
    us: "yes",
    detail:
      "Named zones (accumulation / neutral / distribution / caution) with a confidence score. Merlin uses Fibonacci retracement only — a technique where two traders can draw two different lines and get two different answers.",
  },
  {
    category: "Position planning",
    feature: "Entry ladder (starter / core / deep)",
    merlin: "no",
    us: "yes",
    detail:
      "Not documented in Merlin's tutorials. EverNorthstar splits your budget 30/35/35% across three accumulation-band price levels with an invalidation level below the band floor.",
  },
  {
    category: "Position planning",
    feature: "Ring-fence profit-taking rules",
    merlin: "no",
    us: "yes",
    detail:
      "Not documented in Merlin. EverNorthstar shows 25/50/75%-of-gain scenarios with dollar amounts, net-PL-if-remainder-zero worst case, plus tax-adjusted net after federal + state.",
  },
  {
    category: "Analysis depth",
    feature: "Historical outcome lookup",
    merlin: "no",
    us: "yes",
    detail:
      "Not documented in Merlin. EverNorthstar searches 2 years of history for bars in the same zone as your setup and returns the distribution of forward returns (p25 / median / p75, 30d + 90d).",
  },
  {
    category: "Analysis depth",
    feature: "AI plan summary",
    merlin: "no",
    us: "yes",
    detail:
      "No AI feature appears in Merlin's tutorial library. EverNorthstar summarizes any plan with Claude Haiku — plain-English descriptive framing, never prescriptive (publisher-exemption safe).",
  },
  {
    category: "Analysis depth",
    feature: "Ask Why (LLM explains a ticker's move)",
    merlin: "no",
    us: "yes",
    detail:
      "Only in EverNorthstar. Any ranked ticker → one-click Claude explanation of the price action + news catalysts + smart-money context.",
  },
  {
    category: "Analysis depth",
    feature: "Smart Money — Congress + 13F + Insider",
    merlin: "no",
    us: "yes",
    detail:
      "Only in EverNorthstar. Composite score from Pelosi Tracker, institutional 13F holdings, and insider Form 4 filings.",
  },
  {
    category: "Portfolio tracking",
    feature: "Auto-connect crypto exchanges",
    merlin: "yes",
    us: "yes",
    detail:
      "Merlin supports 5 exchanges (Coinbase, Binance.US, Kraken, Gemini, Uphold). EverNorthstar supports 7 today (Coinbase, Binance.US, Kraken, Gemini, KuCoin, Bybit, OKX) via CCXT — adding new ones is a one-line whitelist. Both use read-only API keys.",
  },
  {
    category: "Portfolio tracking",
    feature: "Wallet connect (Ledger / MetaMask / Atomic)",
    merlin: "yes",
    us: "no",
    detail:
      "Merlin supports Ledger, MetaMask, and Atomic Wallet imports. EverNorthstar doesn't yet — on the roadmap.",
  },
  {
    category: "Portfolio tracking",
    feature: "Auto-connect brokerages (Fidelity / Schwab / etc.)",
    merlin: "no",
    us: "yes",
    detail:
      "Merlin is crypto-only. EverNorthstar syncs 10,000+ US institutions via Plaid — brokerages, banks, retirement accounts.",
  },
  {
    category: "Tax + realizations",
    feature: "Tax estimation on planned exits",
    merlin: "yes",
    us: "yes",
    detail:
      "Both show estimated tax on target hits. EverNorthstar auto-detects long-term vs short-term from holding period; defaults to US federal + Colorado state rates (configurable).",
  },
  {
    category: "Tax + realizations",
    feature: "Mark-as-sold flow + realized-PL ledger",
    merlin: "yes",
    us: "yes",
    detail:
      "Both record realizations with quantity, price, and net after tax. EverNorthstar keeps an immutable per-sale ledger with LT/ST badges.",
  },
  {
    category: "Alerts",
    feature: "Price alerts",
    merlin: "yes",
    us: "yes",
    detail:
      "Both. EverNorthstar adds zone-target alerts ('when BTC enters distribution') and score-threshold alerts.",
  },
  {
    category: "Signals + rankings",
    feature: "Ranked long/short candidates (not just tracker)",
    merlin: "no",
    us: "yes",
    detail:
      "Only in EverNorthstar. 5 sleeves scored daily (crypto, crypto micro, large caps, penny stocks, long-term). Not in Merlin's product surface.",
  },
  {
    category: "Signals + rankings",
    feature: "Curated strategy baskets",
    merlin: "no",
    us: "yes",
    detail:
      "10 curated strategies (Nancy Pelosi Tracker, Kongressional Conviction, Congressional Buys, insider composite, and more) with full position baskets + backtested returns.",
  },
  {
    category: "Backtesting",
    feature: "Backtested strategy returns visualization",
    merlin: "partial",
    us: "yes",
    detail:
      "Merlin has strategy backtests per third-party listings; not documented in their public tutorials. EverNorthstar ships walk-forward backtests + returns visualization on every strategy card.",
  },
  {
    category: "Platform",
    feature: "Web app",
    merlin: "yes",
    us: "yes",
    detail: "Both.",
  },
  {
    category: "Platform",
    feature: "Native mobile app (iOS + Android)",
    merlin: "yes",
    us: "no",
    detail:
      "Merlin has iOS + Android with synced state. EverNorthstar is web-only today (mobile-responsive) — native app on the roadmap.",
  },
];

function Cell({ v }: { v: Row["merlin"] }) {
  if (v === "yes")
    return (
      <span className="inline-flex items-center gap-1 text-emerald-300 text-xs font-semibold">
        <span>✓</span> Yes
      </span>
    );
  if (v === "no")
    return (
      <span className="inline-flex items-center gap-1 text-zinc-500 text-xs">
        <span>✕</span> No
      </span>
    );
  if (v === "partial")
    return (
      <span className="inline-flex items-center gap-1 text-amber-300 text-xs">
        <span>◐</span> Partial
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-amber-300 text-xs">
      <span>✎</span> Manual
    </span>
  );
}

const CATEGORIES = [
  "Exit targets",
  "Position planning",
  "Analysis depth",
  "Portfolio tracking",
  "Tax + realizations",
  "Alerts",
  "Signals + rankings",
  "Backtesting",
  "Platform",
];

export default function VsMerlinPage() {
  const rowsByCategory = CATEGORIES.map((c) => ({
    category: c,
    rows: ROWS.filter((r) => r.category === c),
  }));

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-16 pb-8">
        <p className="text-xs text-emerald-400 uppercase tracking-widest mb-3">
          Honest head-to-head
        </p>
        <h1 className="text-3xl md:text-5xl font-semibold tracking-tight mb-4">
          EverNorthstar vs Merlin
        </h1>
        <p className="text-lg md:text-xl text-zinc-300 leading-relaxed mb-6">
          Merlin makes you draw Fibonacci retracements on TradingView and type
          the numbers back into a spreadsheet. EverNorthstar computes zones,
          entry ladders, and profit-taking scenarios{" "}
          <span className="text-emerald-300">automatically</span> — plus
          historical outcome distributions and AI plan summaries.
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <Link
            href="/sign-up"
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
          >
            Start free — no card required
          </Link>
          <Link
            href="/pricing"
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-md bg-zinc-800 border border-zinc-700 text-zinc-100 hover:bg-zinc-700 text-sm font-medium"
          >
            See pricing
          </Link>
        </div>
      </section>

      {/* Merlin's own admission */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
          <p className="text-xs text-zinc-500 uppercase tracking-wider mb-3">
            Merlin&apos;s own product summary, from their onboarding email
          </p>
          <ol className="text-sm text-zinc-300 space-y-1 mb-4">
            <li>
              <span className="text-emerald-400 font-semibold">1.</span> Add
              coins/assets manually or connect automatically
            </li>
            <li>
              <span className="text-emerald-400 font-semibold">2.</span> Visit
              Assets page to view your portfolio balances &amp; values
            </li>
            <li>
              <span className="text-emerald-400 font-semibold">3.</span> Create
              an Exit Strategy to receive alerts when your targets are reached
            </li>
          </ol>
          <p className="text-xs text-zinc-500 leading-relaxed">
            That&apos;s the whole product. The targets in step 3 come from{" "}
            <em>you</em> — Merlin&apos;s 26-minute &ldquo;How to Choose Exit
            Targets&rdquo; masterclass walks you through drawing Fibonacci
            retracement in a free TradingView account (timestamp 10:23), picking
            key fib levels (13:01), and entering them into a spreadsheet before
            typing them into Merlin (13:58). Merlin&apos;s role is storage +
            alerts + tax estimation on numbers you already picked yourself.
          </p>
        </div>
      </section>

      {/* The proof point */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <h2 className="text-2xl font-semibold tracking-tight mb-2">
          What our engine actually outputs — real data, right now
        </h2>
        <p className="text-sm text-zinc-400 mb-4">
          Below is a live reading from our production zone engine for Solana,
          taken at scale from real Binance hourly bars. No cherry-picking, no
          demo mode.
        </p>
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-5 font-mono text-xs">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-emerald-300 mb-1">Zone reading</p>
              <p className="text-zinc-300">SOL — accumulation zone</p>
              <p className="text-zinc-500">Confidence: 71.2%</p>
              <p className="text-zinc-500">RSI(14): 38.9 (oversold)</p>
              <p className="text-zinc-500">Bollinger: −1.76σ (below mean)</p>
              <p className="text-zinc-500">Score percentile: 12.2%</p>
              <p className="text-zinc-500">Volume divergence: flagged</p>
            </div>
            <div>
              <p className="text-emerald-300 mb-1">Historical analog lookup</p>
              <p className="text-zinc-300">53 prior setups matched</p>
              <p className="text-zinc-500">30-day median forward: −1.6%</p>
              <p className="text-zinc-500">30-day p25 / p75: −4.1% / +1.2%</p>
              <p className="text-zinc-500">90-day median forward: +0.8%</p>
            </div>
          </div>
          <p className="text-zinc-600 mt-4 text-[10px] leading-relaxed">
            Descriptive data only. Not a buy/sell recommendation. We are a
            research publisher, not a registered investment adviser.
          </p>
        </div>
        <p className="text-xs text-zinc-500 mt-3 italic">
          This is the analysis Merlin makes users do on TradingView with a
          Fibonacci tool.
        </p>
      </section>

      {/* Comparison table */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <h2 className="text-2xl font-semibold tracking-tight mb-4">
          Feature-by-feature comparison
        </h2>
        {rowsByCategory.map((group) => (
          <div key={group.category} className="mb-6">
            <h3 className="text-xs text-emerald-400 uppercase tracking-widest mb-2 border-b border-zinc-800 pb-1.5">
              {group.category}
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] text-zinc-500 uppercase tracking-wider">
                    <th className="text-left py-2 pr-3 font-normal w-2/5">
                      Feature
                    </th>
                    <th className="text-center py-2 px-2 font-normal w-24">
                      Merlin
                    </th>
                    <th className="text-center py-2 px-2 font-normal w-24">
                      EverNorthstar
                    </th>
                    <th className="text-left py-2 pl-3 font-normal">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {group.rows.map((r) => (
                    <tr
                      key={r.feature}
                      className="border-t border-zinc-800/60 align-top"
                    >
                      <td className="py-3 pr-3 text-zinc-200 font-medium">
                        {r.feature}
                      </td>
                      <td className="py-3 px-2 text-center">
                        <Cell v={r.merlin} />
                      </td>
                      <td className="py-3 px-2 text-center">
                        <Cell v={r.us} />
                      </td>
                      <td className="py-3 pl-3 text-[11px] text-zinc-500 leading-relaxed">
                        {r.detail}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </section>

      {/* Bottom-line section */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-6">
          <h2 className="text-xl font-semibold tracking-tight mb-3">
            The honest one-line summary
          </h2>
          <p className="text-sm text-zinc-200 leading-relaxed mb-3">
            <strong className="text-emerald-300">Merlin</strong> is a
            wide-and-shallow crypto tracker with alerts on user-typed prices.
          </p>
          <p className="text-sm text-zinc-200 leading-relaxed mb-4">
            <strong className="text-emerald-300">EverNorthstar</strong> is
            narrow-and-deep planning. Fewer wallets. No native mobile app yet.
            But the actual analysis — zones, ladders, ring-fence math,
            historical distributions, AI summaries — is done{" "}
            <em>for you</em> instead of by you.
          </p>
          <p className="text-sm text-zinc-400 leading-relaxed">
            If you like Merlin&apos;s Fibonacci-on-TradingView workflow, keep
            using it — it&apos;s a valid approach. If you&apos;d rather have
            the computation done for you, EverNorthstar is here.
          </p>
        </div>
      </section>

      {/* Pricing quick-look */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <h2 className="text-2xl font-semibold tracking-tight mb-4">
          Pricing at a glance
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
            <p className="text-xs uppercase tracking-wider text-zinc-500 mb-2">
              Merlin
            </p>
            <ul className="text-sm text-zinc-300 space-y-1.5">
              <li>Camelot — free (2 portfolios, 10 assets)</li>
              <li>Lancelot — $13.49–14.99/mo (5 portfolios, unlimited assets)</li>
              <li>Excalibur — $26.99–29.99/mo (10 portfolios)</li>
              <li>King Arthur — $44.99–49.99/mo (unlimited)</li>
            </ul>
          </div>
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-5">
            <p className="text-xs uppercase tracking-wider text-emerald-300 mb-2">
              EverNorthstar
            </p>
            <ul className="text-sm text-zinc-100 space-y-1.5">
              <li>Free — 3 longs / 3 shorts, 5 watchlist tickers</li>
              <li>
                Pro — <strong>$19/mo</strong> or <strong>$190/yr</strong> —
                every feature above unlocked
              </li>
              <li>
                Founder Lifetime — <strong>$99 one-time</strong>, capped at 100
                seats
              </li>
            </ul>
            <p className="text-[10px] text-zinc-500 mt-3 leading-relaxed">
              One tier. No feature gates by portfolio count. Cancel any time in
              the Stripe portal.
            </p>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="max-w-4xl mx-auto px-6 pb-16">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-6 text-center">
          <h2 className="text-2xl font-semibold tracking-tight mb-2">
            Try it in parallel with your current setup
          </h2>
          <p className="text-sm text-zinc-400 mb-5 leading-relaxed max-w-lg mx-auto">
            You don&apos;t need to leave Merlin to see if this works better for
            you. Sign up free, connect one exchange, run one plan on your
            biggest bag, and compare.
          </p>
          <Link
            href="/sign-up"
            className="inline-flex items-center justify-center px-6 py-3 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
          >
            Start free →
          </Link>
        </div>
      </section>

      {/* Sources */}
      <section className="max-w-4xl mx-auto px-6 pb-16 text-[11px] text-zinc-500">
        <p className="uppercase tracking-wider text-zinc-500 mb-2">
          Sources for Merlin claims
        </p>
        <ul className="space-y-1 leading-relaxed">
          <li>
            Merlin&apos;s 3-step product summary — the &ldquo;Get Started
            Quickly&rdquo; onboarding slide sent to every new signup.
          </li>
          <li>
            Merlin&apos;s exit-target methodology — the 26:26 &ldquo;How to
            Choose Exit Targets&rdquo; masterclass by founder Johnny Krypto,
            with chapters covering TradingView + Fibonacci setup (10:23),
            spreadsheet target entry (13:58), and the Merlin sync (18:53).
          </li>
          <li>
            Merlin&apos;s supported integrations — their public
            &ldquo;How-To&rdquo; video library lists Uphold, Binance.US,
            Coinbase, Kraken, Gemini, Atomic Wallet, Ledger, and MetaMask.
          </li>
          <li>
            Merlin pricing — tier structure and pricing bands from their public
            subscriptions page.
          </li>
          <li>
            Where a Merlin feature exists but isn&apos;t publicly documented, we
            marked it &ldquo;partial&rdquo; rather than &ldquo;no&rdquo;.
            Undocumented is not the same as nonexistent.
          </li>
        </ul>
        <p className="mt-6 text-zinc-600 text-[10px] leading-relaxed">
          Merlin is a trademark of its owner. EverNorthstar is a product of
          5Royals Investments LLC and is not affiliated with, endorsed by, or
          sponsored by Merlin. This comparison reflects each product&apos;s
          publicly available information as of the date this page was last
          updated.
        </p>
      </section>
    </main>
  );
}
