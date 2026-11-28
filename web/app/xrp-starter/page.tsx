import type { Metadata } from "next";
import Link from "next/link";

// Free lead magnet into /xrpl + /sign-up. The whole page is ungated so
// it reads as a public resource (good for SEO, shareability), but every
// section earns the reader toward the email capture in the hero and the
// "get the weekly digest" block at the bottom.
//
// Positioning: honest, primary-source-first, tiered, dated. Deliberately
// the opposite of the Jake Claver / Crypto Phoenix / MaximusCrypto-style
// link-dump "playbooks" circulating in the XRP corner of the internet.

export const metadata: Metadata = {
  title: "The Honest XRP Starter Kit — Primary Sources, Tiered | EverNorthstar",
  description:
    "The curated XRP reading list for serious holders: Ripple, XRPL Foundation, BIS, Moody's, OCC, SEC filings — tiered by trust, dated, zero affiliate links, zero price hype. Free from EverNorthstar.",
  openGraph: {
    title: "The Honest XRP Starter Kit — Primary Sources, Tiered",
    description:
      "The XRP reading list without the $500 price-target hype. Primary sources first, tiered by trust, every link dated and explained.",
    url: "https://evernorthstar.app/xrp-starter",
    siteName: "EverNorthstar",
    type: "article",
  },
  alternates: {
    canonical: "https://evernorthstar.app/xrp-starter",
  },
};

// --------------------------------------------------------------------- //
// Content
// --------------------------------------------------------------------- //

type Resource = {
  title: string;
  publisher: string;
  url: string;
  why: string;
  date?: string;
};

// Tier 1: official, filable, primary. Read these before anything else.
const PRIMARY: Resource[] = [
  {
    title: "XRP Ledger documentation",
    publisher: "XRPL Foundation",
    url: "https://xrpl.org/docs.html",
    why: "The protocol itself, in plain language. Start here before any YouTube video.",
  },
  {
    title: "XRPL blog — amendments & roadmap",
    publisher: "XRPL Foundation",
    url: "https://xrpl.org/blog",
    why: "Validator votes, protocol upgrades (XLS-65 SingleAssetVault, XLS-66 Lending), and Default UNL changes — the ground truth for \"what's actually shipping.\"",
  },
  {
    title: "Ripple press releases",
    publisher: "Ripple",
    url: "https://ripple.com/insights/",
    why: "Named bank integrations, Ripple Prime, Ripple Custody, Trust Bank milestones. Primary source for \"did this partnership actually get announced.\"",
  },
  {
    title: "RLUSD transparency page",
    publisher: "Ripple",
    url: "https://ripple.com/products/stablecoin/transparency/",
    why: "Live attestations and reserve composition for Ripple USD — the stablecoin now sitting on the XRPL.",
  },
  {
    title: "Moody's A2/P-1 rating of RLUSD",
    publisher: "Moody's Ratings",
    url: "https://ratings.moodys.com/",
    why: "First investment-grade credit rating ever assigned to a stablecoin. Changes what institutions can hold.",
    date: "Oct 28 2026",
  },
  {
    title: "OCC approval — Ripple National Trust Bank",
    publisher: "Office of the Comptroller of the Currency",
    url: "https://www.occ.gov/news-events/newsroom/index.html",
    why: "Federally regulated banking charter for Ripple. Unlocks custody and fiat rails outside the stablecoin issuer sandbox.",
    date: "Oct 2026",
  },
  {
    title: "US spot XRP ETF prospectuses (SEC EDGAR)",
    publisher: "SEC EDGAR",
    url: "https://www.sec.gov/edgar/search/",
    why: "Search filings from Canary, Bitwise, Franklin Templeton, Grayscale. Primary source for ETF mechanics, fees, custody arrangements.",
  },
  {
    title: "BIS Working Paper 1374 — Verifiable Official Statistics",
    publisher: "Bank for International Settlements",
    url: "https://www.bis.org/publ/work1374.htm",
    why: "BIS tested the XRPL for anchoring official-statistics attestations. Matters because central banks explored using it.",
  },
];

// Tier 2: outlets that do original reporting + verify sources.
const JOURNALISM: Resource[] = [
  {
    title: "Decrypt — XRP + Ripple coverage",
    publisher: "Decrypt",
    url: "https://decrypt.co/search?q=XRP",
    why: "Covers Schwartz interviews, Ripple product launches, and SEC/CFTC actions with attribution.",
  },
  {
    title: "CoinDesk — ETF + institutional coverage",
    publisher: "CoinDesk",
    url: "https://www.coindesk.com/tag/xrp",
    why: "Best shop for ETF inflow/outflow reporting and institutional-desk commentary.",
  },
  {
    title: "The Block — on-chain + institutional data",
    publisher: "The Block",
    url: "https://www.theblock.co/search?query=xrp",
    why: "Deep reporting on institutional XRP flows, Ripple partnerships, and Hidden Road / Ripple Prime.",
  },
  {
    title: "Reuters — Ripple + XRP wire coverage",
    publisher: "Reuters",
    url: "https://www.reuters.com/site-search/?query=ripple+xrp",
    why: "Wire-service standard: multi-source, usually first to confirm bank partnerships.",
  },
  {
    title: "Bloomberg — stablecoin + tokenization coverage",
    publisher: "Bloomberg",
    url: "https://www.bloomberg.com/search?query=RLUSD",
    why: "Best coverage for RLUSD institutional adoption and Standard Chartered / BNY Mellon integrations.",
  },
];

// Tier 3: analysis shops that publish original research on XRPL/Ripple.
const ANALYSIS: Resource[] = [
  {
    title: "Messari — XRPL quarterly reports",
    publisher: "Messari",
    url: "https://messari.io/project/ripple",
    why: "Quarterly XRPL state-of-the-network reports. Rigorous methodology, cited data.",
  },
  {
    title: "rwa.xyz — XRPL tokenized asset dashboard",
    publisher: "rwa.xyz",
    url: "https://app.rwa.xyz/networks/xrp-ledger",
    why: "The honest on-chain measure of tokenized real-world assets on XRPL (concentration risks visible too).",
  },
  {
    title: "SoSoValue — US spot XRP ETF flows",
    publisher: "SoSoValue",
    url: "https://sosovalue.com/assets/etf/us-xrp-spot",
    why: "Daily net assets and flows across all US spot XRP ETF issuers. Updated same-day.",
  },
  {
    title: "CoinGecko — RLUSD supply + price",
    publisher: "CoinGecko",
    url: "https://www.coingecko.com/en/coins/ripple-usd",
    why: "Authoritative circulating supply + market cap for RLUSD; API is free.",
  },
  {
    title: "DeFiLlama — XRPL TVL",
    publisher: "DeFiLlama",
    url: "https://defillama.com/chain/XRPL",
    why: "Cross-chain TVL comparison. Useful for contextualizing XRPL vs. Ethereum, Solana, Stellar on tokenized assets.",
  },
  {
    title: "XRPSCAN — XRPL block explorer",
    publisher: "XRPSCAN",
    url: "https://xrpscan.com/",
    why: "Explore validators, amendments, transaction volumes, token issuances on-chain.",
  },
];

// Tier 4: signal to buyer. All US-regulated, no affiliate links — picked
// on custody quality, regulatory posture, and spread transparency.
const WHERE_TO_BUY: Resource[] = [
  {
    title: "Coinbase",
    publisher: "US-regulated exchange · publicly listed",
    url: "https://www.coinbase.com/price/xrp",
    why: "Deepest US-market liquidity. Fees higher than Kraken Pro but cleanest regulatory posture.",
  },
  {
    title: "Kraken Pro",
    publisher: "US-regulated exchange",
    url: "https://pro.kraken.com/",
    why: "Lower fees than Coinbase for anyone above the casual tier; strong operational history.",
  },
  {
    title: "Gemini",
    publisher: "US-regulated exchange · NYDFS licensed",
    url: "https://www.gemini.com/prices/xrp",
    why: "Strong compliance track record. Useful alternative if you want to split custody across venues.",
  },
  {
    title: "Alto IRA — self-directed crypto IRA",
    publisher: "Retirement account",
    url: "https://www.altoira.com/",
    why: "Tax-advantaged XRP exposure in an IRA. Research the fee structure carefully — adds up at small balances.",
  },
];

// Self-custody picks. Hardware only; software wallets are for small balances
// or active trading, not for long-term core positions.
const COLD_STORAGE: Resource[] = [
  {
    title: "Ledger Nano X / Nano S Plus",
    publisher: "Ledger · hardware wallet",
    url: "https://www.ledger.com/",
    why: "Largest install base. Buy directly from ledger.com, never from Amazon or resellers — supply-chain risk is real.",
  },
  {
    title: "Trezor Safe 5 / Model T",
    publisher: "Trezor · hardware wallet",
    url: "https://trezor.io/",
    why: "Open-source firmware. Doesn't natively support XRP through the Trezor Suite — you use it via an external XRPL interface, which adds friction.",
  },
  {
    title: "D'CENT Biometric Wallet",
    publisher: "D'CENT · hardware wallet",
    url: "https://dcentwallet.com/",
    why: "Native XRP support including trust lines and the XRPL DEX. Smaller company — read reviews before committing serious balances.",
  },
];

// --------------------------------------------------------------------- //
// What to avoid — the honest half of the playbook
// --------------------------------------------------------------------- //

const RED_FLAGS: Array<{ pattern: string; why: string }> = [
  {
    pattern: "Specific-dollar price predictions (\"XRP to $589\", \"$1,000 XRP by Q2\")",
    why: "No one knows. Confident price targets are a selling tool, not analysis — even when wrapped in charts or \"models.\"",
  },
  {
    pattern: "\"Riddles,\" \"domino theory,\" \"quantum financial system,\" \"GESARA/NESARA\"",
    why: "These are narrative buckets that absorb any news as \"proof.\" Treat anyone leaning on them as entertainment, not information.",
  },
  {
    pattern: "Anonymous X accounts with large followings and no track record",
    why: "Great anonymous analysts exist, but new holders can't tell them apart from paid shills. Default to named journalists and official sources until you can.",
  },
  {
    pattern: "\"Only video you'll ever need\"-style hero content",
    why: "XRPL changes fast (amendments, integrations, ETF flows). One video is never \"all you need\" on a moving target.",
  },
  {
    pattern: "Paid Telegram / Discord groups selling signals",
    why: "If the signals were any good, the operator wouldn't need subscription income. Nearly all are affiliate-funnel operations.",
  },
];

// --------------------------------------------------------------------- //
// Components
// --------------------------------------------------------------------- //

function TierCard({
  title,
  subtitle,
  tier,
  items,
}: {
  title: string;
  subtitle: string;
  tier: string;
  items: Resource[];
}) {
  return (
    <section className="mb-8">
      <div className="flex items-baseline gap-3 mb-1">
        <span className="text-[10px] uppercase tracking-widest text-emerald-400 font-semibold">
          {tier}
        </span>
        <h2 className="text-2xl font-semibold tracking-tight text-zinc-100">{title}</h2>
      </div>
      <p className="text-sm text-zinc-400 mb-4 max-w-2xl leading-relaxed">{subtitle}</p>
      <ul className="space-y-3">
        {items.map((r) => (
          <li
            key={r.url}
            className="rounded-lg border border-zinc-800 bg-zinc-900/40 hover:border-emerald-500/40 hover:bg-emerald-500/5 transition p-4"
          >
            <a href={r.url} target="_blank" rel="noopener noreferrer" className="block">
              <div className="flex items-baseline justify-between gap-3 mb-1">
                <p className="text-sm font-semibold text-zinc-100">{r.title}</p>
                {r.date && (
                  <p className="text-[11px] text-emerald-300 whitespace-nowrap tabular-nums">
                    {r.date}
                  </p>
                )}
              </div>
              <p className="text-[11px] uppercase tracking-wider text-zinc-500 mb-2">
                {r.publisher}
              </p>
              <p className="text-[13px] text-zinc-300 leading-snug">{r.why}</p>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

// --------------------------------------------------------------------- //
// Page
// --------------------------------------------------------------------- //

export default function XrpStarterPage() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-16 pb-10">
        <p className="text-xs uppercase tracking-widest text-emerald-400 mb-3">
          Free · The Honest XRP Starter Kit
        </p>
        <h1 className="text-3xl md:text-5xl font-semibold tracking-tight mb-5 leading-tight">
          The XRP reading list{" "}
          <span className="text-emerald-300">
            without the $500 price-target hype
          </span>
        </h1>
        <p className="text-lg md:text-xl text-zinc-300 leading-relaxed mb-6 max-w-3xl">
          Every link here is a primary source, a reputable outlet, or a transparent
          data shop. Tiered by trust. Dated where it matters. Zero affiliate links.
          Zero anonymous influencer videos. Built for people who actually hold XRP
          as part of a serious portfolio.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <Link
            href="/sign-up?utm_source=xrp-starter"
            className="inline-flex items-center justify-center px-5 py-3 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
          >
            Get the weekly XRP update → free
          </Link>
          <Link
            href="/xrpl"
            className="inline-flex items-center justify-center px-5 py-3 rounded-md bg-zinc-800 border border-zinc-700 text-zinc-100 hover:bg-zinc-700 text-sm font-medium"
          >
            See the live XRPL adoption tracker →
          </Link>
        </div>
        <p className="text-xs text-zinc-500 leading-relaxed max-w-2xl">
          Published by{" "}
          <Link href="/" className="text-zinc-400 hover:text-emerald-300 underline underline-offset-2">
            EverNorthstar
          </Link>
          , a research publisher under the Lowe v. SEC publisher exemption. We are
          NOT a registered investment adviser. This is an educational resource list,
          not financial advice.
        </p>
      </section>

      {/* Why this is different */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-6">
          <h2 className="text-lg font-semibold tracking-tight mb-3 text-emerald-100">
            How this kit is different
          </h2>
          <ul className="space-y-2 text-sm text-zinc-300 leading-relaxed">
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span>
                <strong className="text-zinc-100">Primary sources first.</strong>{" "}
                Ripple, XRPL Foundation, BIS, Moody&apos;s, OCC, SEC filings — not
                a YouTube reaction channel.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span>
                <strong className="text-zinc-100">Tiered by trust.</strong> You
                always know whether you&apos;re reading journalism, analysis, or
                commentary.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span>
                <strong className="text-zinc-100">Dated.</strong> Resources that
                are time-sensitive have the date they reference.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span>
                <strong className="text-zinc-100">Zero affiliate links.</strong>{" "}
                No kickbacks to exchanges, wallets, or IRAs. Pick what fits you.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400 mt-0.5">✓</span>
              <span>
                <strong className="text-zinc-100">Honest about what to avoid.</strong>{" "}
                Scroll to the bottom for the red-flag patterns worth skipping.
              </span>
            </li>
          </ul>
        </div>
      </section>

      {/* Tiered sources */}
      <section className="max-w-4xl mx-auto px-6">
        <TierCard
          tier="Tier 1"
          title="Primary sources — read these first"
          subtitle="Official documentation, regulator filings, and ratings-agency reports. These are the ground truth: everything downstream cites back to them."
          items={PRIMARY}
        />
        <TierCard
          tier="Tier 2"
          title="Trusted journalism"
          subtitle="Outlets that do original reporting and name their sources. Use these to track announcements as they happen."
          items={JOURNALISM}
        />
        <TierCard
          tier="Tier 3"
          title="Data + analysis shops"
          subtitle="Independent research firms and transparent data dashboards. Verify claims from journalism against these."
          items={ANALYSIS}
        />
      </section>

      {/* Mid-page CTA */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-6 text-center">
          <h2 className="text-lg font-semibold tracking-tight mb-2">
            Want the live data behind all of this?
          </h2>
          <p className="text-sm text-zinc-300 mb-4 leading-relaxed max-w-lg mx-auto">
            The{" "}
            <Link href="/xrpl" className="text-emerald-300 underline underline-offset-2 hover:text-emerald-200">
              EverNorthstar XRPL Adoption Tracker
            </Link>{" "}
            auto-refreshes every 6 hours from the same sources above — amendment
            status, RLUSD supply, ETF flows, tokenized RWA value.
          </p>
          <Link
            href="/xrpl"
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
          >
            Open the tracker →
          </Link>
        </div>
      </section>

      {/* Where to buy + custody */}
      <section className="max-w-4xl mx-auto px-6">
        <TierCard
          tier="Logistics"
          title="Where to buy — US-regulated venues"
          subtitle="No affiliate links. Picked on regulatory posture, spread transparency, and operational history. Always start with the smallest test transfer that matters."
          items={WHERE_TO_BUY}
        />
        <TierCard
          tier="Self-custody"
          title="Cold storage picks"
          subtitle="Hardware-only. Buy directly from the manufacturer — never Amazon or resellers. Write the seed phrase on paper or steel, never in a photo or cloud note."
          items={COLD_STORAGE}
        />
      </section>

      {/* Red flags */}
      <section className="max-w-4xl mx-auto px-6 pb-10">
        <div className="flex items-baseline gap-3 mb-1">
          <span className="text-[10px] uppercase tracking-widest text-rose-400 font-semibold">
            The other half
          </span>
          <h2 className="text-2xl font-semibold tracking-tight text-zinc-100">
            What to avoid
          </h2>
        </div>
        <p className="text-sm text-zinc-400 mb-4 max-w-2xl leading-relaxed">
          Most &quot;XRP playbooks&quot; floating around are curated by affiliate
          marketers, anonymous X accounts, or hype creators. Here&apos;s the
          pattern-matching to protect your attention budget:
        </p>
        <ul className="space-y-3">
          {RED_FLAGS.map((r) => (
            <li
              key={r.pattern}
              className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-4"
            >
              <p className="text-sm font-semibold text-rose-200 mb-1">{r.pattern}</p>
              <p className="text-[13px] text-zinc-300 leading-snug">{r.why}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* Final CTA */}
      <section className="max-w-3xl mx-auto px-6 pb-16">
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-6 text-center">
          <h2 className="text-xl font-semibold tracking-tight mb-2">
            Get the weekly honest XRP update
          </h2>
          <p className="text-sm text-zinc-400 mb-5 leading-relaxed max-w-lg mx-auto">
            Primary-source summary every Monday: amendment votes, ETF flows,
            tokenized RWA growth, new bank integrations. Same tier discipline as
            this kit. One email per week. Free.
          </p>
          <Link
            href="/sign-up?utm_source=xrp-starter-footer"
            className="inline-flex items-center justify-center px-6 py-3 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium"
          >
            Sign up free → get the digest
          </Link>
          <p className="text-[11px] text-zinc-600 mt-3 leading-relaxed">
            Signing up also unlocks the full EverNorthstar dashboard — rankings,
            zones, Smart Money data, portfolio-aware position planner.
          </p>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="max-w-4xl mx-auto px-6 pb-16 text-[12px] text-zinc-500">
        <h3 className="text-sm uppercase tracking-wider text-zinc-400 mb-3">
          About this kit
        </h3>
        <div className="space-y-3 leading-relaxed">
          <p>
            <strong className="text-zinc-300">Educational only.</strong>{" "}
            EverNorthstar is a research publisher under the Lowe v. SEC publisher
            exemption. We are not a registered investment adviser, broker-dealer,
            or any other financial institution. Nothing here is a recommendation
            to buy or sell XRP, RLUSD, any ETF, or any other instrument.
          </p>
          <p>
            <strong className="text-zinc-300">No affiliate links.</strong> We do
            not receive compensation from any of the exchanges, wallets, IRA
            custodians, outlets, or data providers linked above. If we ever add
            compensated links, they will be disclosed inline at the point of the
            link.
          </p>
          <p>
            <strong className="text-zinc-300">Resources rot.</strong> Dated items
            are accurate as of that date. Undated items are maintained lists
            (publisher landing pages) that stay relevant across changes. We update
            this kit as the ecosystem changes — subscribe to catch it.
          </p>
          <p className="pt-3 text-[11px] text-zinc-600">
            Published by EverNorthstar, a product of 5 Royals Investments Digital
            (Wyoming) and its Texas operating entity.
          </p>
        </div>
      </section>
    </main>
  );
}
