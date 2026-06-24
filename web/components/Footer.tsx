import Link from "next/link";

/**
 * Site-wide footer. Lives in the root layout so every page (including
 * landing, pricing, legal) renders it. Two purposes:
 *   1. Discoverable legal links — required by Stripe + good for trust.
 *   2. Persistent "this is not financial advice" disclaimer so the user
 *      sees the reminder every time they scroll to the bottom of any page.
 */
export function Footer() {
  return (
    <footer className="border-t border-zinc-800 bg-zinc-950 text-zinc-500 text-xs">
      <div className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-2 md:grid-cols-4 gap-6">
        <div>
          <p className="font-semibold text-zinc-300 mb-2">EverNorthstar</p>
          <p className="text-zinc-500 leading-relaxed">
            Honest signals. Smart money. Always pointing north. ⭐
          </p>
          <p className="text-[10px] text-zinc-600 mt-2">
            A product of 5Royals Investments LLC.
          </p>
        </div>

        <div>
          <p className="font-semibold text-zinc-300 mb-2">Product</p>
          <ul className="space-y-1">
            <li><Link href="/" className="hover:text-zinc-200">Dashboard</Link></li>
            <li><Link href="/pricing" className="hover:text-zinc-200">Pricing</Link></li>
            <li><Link href="/portfolio" className="hover:text-zinc-200">Portfolio (Pro)</Link></li>
            <li><Link href="/account" className="hover:text-zinc-200">Account</Link></li>
          </ul>
        </div>

        <div>
          <p className="font-semibold text-zinc-300 mb-2">Legal</p>
          <ul className="space-y-1">
            <li><Link href="/legal/terms" className="hover:text-zinc-200">Terms of Service</Link></li>
            <li><Link href="/legal/privacy" className="hover:text-zinc-200">Privacy Policy</Link></li>
            <li><Link href="/legal/refunds" className="hover:text-zinc-200">Refund Policy</Link></li>
            <li><Link href="/legal/disclaimer" className="hover:text-zinc-200">Financial Disclaimer</Link></li>
          </ul>
        </div>

        <div>
          <p className="font-semibold text-zinc-300 mb-2">Support</p>
          <ul className="space-y-1">
            <li>
              <a
                href="mailto:support@evernorthstar.app"
                className="hover:text-zinc-200"
              >
                support@evernorthstar.app
              </a>
            </li>
            <li className="text-zinc-600 text-[11px] leading-relaxed pt-1">
              Replies typically within 1 business day.
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-zinc-900 max-w-6xl mx-auto px-6 py-4 text-[11px] leading-relaxed text-zinc-600">
        <p>
          <strong className="text-zinc-500">Not financial advice.</strong>{" "}
          EverNorthstar is a research tool that surfaces public market data and
          proprietary signals. It is not a registered investment adviser or
          broker-dealer. Past performance does not predict future results.
          All investment decisions are yours alone — consult a licensed
          professional before acting. See our{" "}
          <Link href="/legal/disclaimer" className="text-zinc-400 hover:text-zinc-200 underline">
            full disclaimer
          </Link>
          .
        </p>
      </div>
    </footer>
  );
}
