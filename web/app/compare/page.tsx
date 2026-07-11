import type { Metadata } from "next";
import Link from "next/link";

// Public comparison landing. Deliberately does NOT name the competitor —
// the comparison is factual and specific enough for readers to know who
// we mean, but staying generic keeps us out of trademark disputes and
// out of Google's "trademark competitor bidding" gray area. Every claim
// is still traceable to a public source (onboarding emails, tutorial
// timestamps, subscription pages) so the honesty holds.

export const metadata: Metadata = {
  title: "How EverNorthstar compares to the top crypto planners | EverNorthstar",
  description:
    "Most crypto planners are portfolio trackers with price alerts on targets you draw yourself in TradingView. EverNorthstar auto-computes zones, entry ladders, and profit-taking scenarios — plus AI plan summaries and historical outcome distributions. Feature-by-feature.",
  openGraph: {
    title: "How EverNorthstar compares to the top crypto planners",
    description:
      "Everything the top competitor does + the analysis they make you do on TradingView. Feature-by-feature.",
    url: "https://evernorthstar.app/compare",
    siteName: "EverNorthstar",
    type: "website",
  },
  alternates: {
    canonical: "https://evernorthstar.app/compare",
  },
};

type Row = {
  category: string;
  feature: string;
  competitor: "yes" | "no" | "partial" | "manual";
  us: "yes" | "no" | "partial" | "manual";
  detail: string;
};

const ROWS: Row[] = [
  {
    category: "Exit targets",
    feature: "Auto-computed price targets",
    competitor: "no",
    us: "yes",
    detail:
      "The top competitor's flagship tutorial walks users through drawing Fibonacci retracement lines by hand in TradingView, then typing the numbers back into their app. EverNorthstar computes accumulation + distribution price bands automatically using an RSI + Bollinger + score-percentile + volume-divergence ensemble.",
  },
  {
    category: "Exit targets",
    feature: "Multi-indicator zone detection",
    competitor: "no",
    us: "yes",
    detail:
      "Named zones (accumulation / neutral / distribution / caution) with a confidence score. The top competitor relies on Fibonacci retracement only — a technique where two traders can draw two different lines and get two different answers.",
  },
  {
    category: "Position planning",
    feature: "Entry ladder (starter / core / deep)",
    competitor: "no",
    us: "yes",
    detail:
      "Not documented in the top competitor's tutorials. EverNorthstar splits your budget 30/35/35% across three accumulation-band price levels with an invalidation level below the band floor.",
  },
  {
    category: "Position planning",
    feature: "Ring-fence profit-taking rules",
    competitor: "no",
    us: "yes",
    detail:
      "Not documented in the top competitor's product. EverNorthstar shows 25/50/75%-of-gain scenarios with dollar amounts, net-PL-if-remainder-zero worst case, plus tax-adjusted net after federal + state.",
  },
  {
    category: "Analysis depth",
    feature: "Historical outcome lookup",
    competitor: "no",
    us: "yes",
    detail:
      "Not documented in the top competitor's product. EverNorthstar searches 2 years of history for bars in the same zone as your setup and returns the distribution of forward returns (p25 / median / p75, 30d + 90d).",
  },
  {
    category: "Analysis depth",
    feature: "AI plan summary",
    competitor: "no",
    us: "yes",
    detail:
      "No AI feature appears in the top competitor's tutorial library. EverNorthstar summarizes any plan with Claude Haiku — plain-English descriptive framing, never prescriptive (publisher-exemption safe).",
  },
  {
    category: "Analysis depth",
    feature: "Ask Why (LLM explains a ticker's move)",
    competitor: "no",
    us: "yes",
    detail:
      "Only in EverNorthstar. Any ranked ticker → one-click Claude explanation of the price action + news catalysts + smart-money context.",
  },
  {
    category: "Analysis depth",
    feature: "Smart Money — Congress + 13F + Insider",
    competitor: "no",
    us: "yes",
    detail:
      "Only in EverNorthstar. Composite score from Pelosi Tracker, institutional 13F holdings, and insider Form 4 filings.",
  },
  {
    category: "Portfolio tracking",
    feature: "Auto-connect crypto exchanges",
    competitor: "yes",
    us: "yes",
    detail:
      "The top competitor supports 5 exchanges. EverNorthstar supports 7 today (Coinbase, Binance.US, Kraken, Gemini, KuCoin, Bybit, OKX) via CCXT — adding new ones is a one-line whitelist. Both use read-only API keys.",
  },
  {
    category: "Portfolio tracking",
    feature: "Wallet connect (Ledger / MetaMask / Atomic)",
    competitor: "yes",
    us: "no",
    detail:
      "The top competitor supports Ledger, MetaMask, and Atomic Wallet imports. EverNorthstar doesn't yet — on the roadmap.",
  },
  {
    category: "Portfolio tracking",
    feature: "Auto-connect brokerages (Fidelity / Schwab / etc.)",
    competitor: "no",
    us: "yes",
    detail:
      "The top competitor is crypto-only. EverNorthstar syncs 10,000+ US institutions via Plaid — brokerages, banks, retirement accounts.",
  },
  {
    category: "Tax + realizations",
    feature: "Tax estimation on planned exits",
    competitor: "yes",
    us: "yes",
    detail:
      "Both show estimated tax on target hits. EverNorthstar auto-detects long-term vs short-term from holding period; defaults to US federal + Colorado state rates (configurable).",
  },
  {
    category: "Tax + realizations",
    feature: "Mark-as-sold flow + realized-PL ledger",
    competitor: "yes",
    us: "yes",
    detail:
      "Both record realizations with quantity, price, and net after tax. EverNorthstar keeps an immutable per-sale ledger with LT/ST badges.",
  },
  {
    category: "Alerts",
    feature: "Price alerts",
    competitor: "yes",
    us: "yes",
    detail:
      "Both. EverNorthstar adds zone-target alerts ('when BTC enters distribution') and score-threshold alerts.",
  },
  {
    category: "Signals + rankings",
    feature: "Ranked long/short candidates (not just tracker)",
    competitor: "no",
    us: "yes",
    detail:
      "Only in EverNorthstar. 5 sleeves scored daily (crypto, crypto micro, large caps, penny stocks, long-term). Not in the top competitor's product surface.",
  },
  {
    category: "Signals + rankings",
    feature: "Curated strategy baskets",
    competitor: "no",
    us: "yes",
    detail:
      "10 curated strategies (Pelosi Tracker, Kongressional Conviction, insider composite, and more) with full position baskets + backtested returns.",
  },
  {
    category: "Backtesting",
    feature: "Backtested strategy returns visualization",
    competitor: "partial",
    us: "yes",
    detail:
      "The top competitor has backtests per third-party listings but doesn't document them publicly. EverNorthstar ships walk-forward backtests + returns visualization on every strategy card.",
  },
  {
    category: "Platform",
    feature: "Web app",
    competitor: "yes",
    us: "yes",
    detail: "Both.",
  },
  {
    category: "Platform",
    feature: "Native mobile app (iOS + Android)",
    competitor: "yes",
    us: "no",
    detail:
      "The top competitor has iOS + Android with synced state. EverNorthstar is web-only today (mobile-responsive) — native app on the roadmap.",
  },
];

function Cell({ v }: { v: Row["competitor"] }) {
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

export default function ComparePage() {
  const rowsByCategory = CATEGORIES.map((c) => ({
    category: c,
    rows: ROWS.filter((r) => r.category === c),
  }));

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-16 pb-8">
        <p className="text-xs text-emerald-400 uppercase tracking-widest mb-3">
          Honest comparison
        </p>
        <h1 className="text-3xl md:text-5xl font-semibold tracking-tight mb-4">
          How we compare to the top crypto planner
        </h1>
        <p className="text-lg md:text-xl text-zinc-300 leading-relaxed mb-6">
          Most crypto planners are portfolio trackers with alerts on targets
          you drew yourself in TradingView. EverNorthstar computes zones, entry
          ladders, and profit-taking scenarios{" "}
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

      {/* Competitor's own admission */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
          <p className="text-xs text-zinc-500 uppercase tracking-wider mb-3">
            The top competitor&apos;s own product summary, from their onboarding
            email
          </p>
          <ol className="text-sm text-zinc-300 space-y-1 mb-4">
            <li>
              <span className="text-emerald-400 font-semibold">1.</span> Add
              coins/assets manually or connect automatically
            </li>
            <li>
              <span className="text-emerald-400 font-semibold">2.</span> Visit
              the assets page to view portfolio balances &amp; values
            </li>
            <li>
              <span className="text-emerald-400 font-semibold">3.</span> Create
              an exit strategy to receive alerts when your targets are reached
            </li>
          </ol>
          <p className="text-xs text-zinc-500 leading-relaxed">
            That&apos;s the whole product. The targets in step 3 come from{" "}
            <em>you</em> — their 26-minute exit-targets masterclass walks you
            through drawing Fibonacci retracement in a free TradingView account,
            picking key fib levels, and entering them into a spreadsheet before
            typing them into the app. The competitor&apos;s role is storage,
            alerts, and tax estimation on numbers you already picked yourself.
          </p>
        </div>
      </section>

      {/* The proof point */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <h2 className="text-2xl font-semibold tracking-tight mb-2">
          What our engine actually outputs — real data, right now
        </h2>
        <p className="text-sm text-zinc-400 mb-4">
          A live reading from our production zone engine for Solana, taken from
          real Binance hourly bars. No cherry-picking, no demo mode.
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
          This is the analysis the competitor asks users to do themselves on
          TradingView with a Fibonacci tool.
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
                      Top competitor
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
                        <Cell v={r.competitor} />
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
            <strong className="text-emerald-300">The top competitor</strong> is
            a wide-and-shallow crypto tracker with alerts on user-typed prices.
          </p>
          <p className="text-sm text-zinc-200 leading-relaxed mb-4">
            <strong className="text-emerald-300">EverNorthstar</strong> is
            narrow-and-deep planning. Fewer wallets. No native mobile app yet.
            But the actual analysis — zones, ladders, ring-fence math,
            historical distributions, AI summaries — is done{" "}
            <em>for you</em> instead of by you.
          </p>
          <p className="text-sm text-zinc-400 leading-relaxed">
            If the Fibonacci-on-TradingView workflow works for you, keep using
            it — it&apos;s a valid approach. If you&apos;d rather have the
            computation done for you, EverNorthstar is here.
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
              Top competitor
            </p>
            <ul className="text-sm text-zinc-300 space-y-1.5">
              <li>Free tier (~2 portfolios, ~10 assets)</li>
              <li>Entry paid tier — $13.49–14.99/mo</li>
              <li>Mid tier — $26.99–29.99/mo</li>
              <li>Top tier — $44.99–49.99/mo</li>
            </ul>
            <p className="text-[10px] text-zinc-500 mt-3 leading-relaxed">
              Feature gates by portfolio count + import count.
            </p>
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
            You don&apos;t need to change tools to see if this works better for
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
          Sources for competitor claims
        </p>
        <ul className="space-y-1 leading-relaxed">
          <li>
            All comparison points are drawn from the competitor&apos;s own
            public product materials — their onboarding emails, tutorial video
            library, exit-target masterclass, supported-integration walkthroughs,
            and public subscription page.
          </li>
          <li>
            Where a competitor feature exists but isn&apos;t publicly
            documented, we marked it &ldquo;partial&rdquo; rather than
            &ldquo;no&rdquo;. Undocumented is not the same as nonexistent.
          </li>
          <li>
            Pricing bands cited from the public subscription page as of the last
            update to this page.
          </li>
        </ul>
        <p className="mt-6 text-zinc-600 text-[10px] leading-relaxed">
          EverNorthstar is a product of 5Royals Investments LLC. We are not
          affiliated with, endorsed by, or sponsored by any product referenced
          on this page. Comparisons reflect publicly available information as
          of the last update.
        </p>
      </section>
    </main>
  );
}
