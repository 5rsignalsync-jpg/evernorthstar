import { LegalPage } from "@/components/LegalPage";

export const metadata = {
  title: "Privacy Policy · EverNorthstar",
  description: "How EverNorthstar collects, uses, and protects your data.",
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" effectiveDate="2026-06-18">
      <p>
        This Privacy Policy describes how 5Royals Investments LLC
        (&quot;EverNorthstar,&quot; &quot;we,&quot; &quot;us&quot;) collects, uses, and shares
        information when you use evernorthstar.app and related services (the
        &quot;Service&quot;).
      </p>

      <h2>1. What we collect</h2>

      <h3>Account information</h3>
      <ul>
        <li>Your email address (used as your login).</li>
        <li>A bcrypt hash of your password — we never store the password in plaintext.</li>
        <li>Your subscription tier and Stripe customer ID (for billing).</li>
        <li>Account preferences (daily-digest opt-in, alert rules you create).</li>
      </ul>

      <h3>Brokerage data (if you connect via Plaid)</h3>
      <ul>
        <li>The institution name (e.g., &quot;Fidelity&quot;), an opaque Plaid item ID, and an encrypted access token.</li>
        <li>Position snapshots — ticker, name, quantity, price, value, cost basis, currency. Refreshed once daily.</li>
        <li>
          <strong>We do not see or store your brokerage username, password,
          or two-factor codes.</strong> Plaid handles authentication directly with
          your bank and only hands us a read-only access token.
        </li>
      </ul>

      <h3>Usage and technical data</h3>
      <ul>
        <li>IP address and approximate location (from your IP) for security + abuse prevention.</li>
        <li>User-agent string and timestamps of requests for rate limiting and debugging.</li>
        <li>Pages you visit and features you use, in aggregated form (no third-party trackers as of the effective date).</li>
      </ul>

      <h3>Payment information</h3>
      <p>
        Payments are processed by <strong>Stripe</strong>. We do not store full card
        numbers — Stripe handles all card data and is PCI DSS Level 1
        compliant. We retain a Stripe customer ID and a redacted summary
        (brand, last four digits) for receipt display.
      </p>

      <h2>2. How we use it</h2>
      <ul>
        <li>To deliver the Service: serve your dashboard, sync your brokerage holdings, send your daily digest, fire your alerts.</li>
        <li>To bill you and prevent fraud.</li>
        <li>To respond to support requests at support@evernorthstar.app.</li>
        <li>To send transactional emails (account confirmation, billing receipts, alerts you opted into).</li>
        <li>To improve the Service in aggregate — for example, debugging slow queries.</li>
      </ul>
      <p>
        <strong>We do not sell your personal information to third parties.</strong> We
        do not show third-party ads and do not run behavioral profiling on you.
      </p>

      <h2>3. Subprocessors</h2>
      <p>We rely on the following service providers (&quot;subprocessors&quot;) to operate the Service:</p>
      <ul>
        <li><strong>Stripe</strong> — payment processing and customer billing.</li>
        <li><strong>Plaid</strong> — read-only brokerage account access (only if you opt in by connecting an account).</li>
        <li><strong>Fly.io</strong> — application hosting and database storage (US-based region: Ashburn, VA).</li>
        <li><strong>Vercel</strong> — frontend hosting and CDN.</li>
        <li><strong>Cloudflare</strong> — DNS management for evernorthstar.app.</li>
        <li><strong>Resend</strong> — outbound transactional email (daily digest, alerts, billing receipts).</li>
        <li><strong>Anthropic</strong> — AI summarization for the Ask Why button, Daily Digest, and Earnings Recap features. Anthropic receives anonymized public market data and our prompt — never your account email, billing details, or brokerage holdings.</li>
        <li><strong>Financial Modeling Prep (FMP)</strong> — fundamentals and Congressional trade data.</li>
        <li><strong>NOWPayments</strong> — optional crypto payment processing (only if you opt to pay with crypto).</li>
      </ul>
      <p>
        Each subprocessor handles a narrow slice of data necessary for their function. We do not authorize them to sell or repurpose your data.
      </p>

      <h2>4. Data retention</h2>
      <ul>
        <li>Account data: retained while your account is active and for up to 90 days after you delete it (for billing reconciliation and abuse investigation).</li>
        <li>Brokerage holdings snapshots: retained as long as the connection is active. Deleted when you disconnect.</li>
        <li>Payment records: retained for 7 years as required by US tax law.</li>
        <li>Logs: retained for up to 30 days.</li>
      </ul>

      <h2>5. Your rights</h2>
      <p>
        Depending on where you live (e.g., California, EU, UK), you may have additional rights:
      </p>
      <ul>
        <li><strong>Access</strong> — request a copy of your personal data.</li>
        <li><strong>Correction</strong> — update inaccurate data.</li>
        <li><strong>Deletion</strong> — request we delete your account and associated data.</li>
        <li><strong>Portability</strong> — receive your data in a machine-readable format.</li>
        <li><strong>Opt-out</strong> — unsubscribe from non-transactional emails at any time.</li>
      </ul>
      <p>
        To exercise any of these, email
        <a href="mailto:support@evernorthstar.app"> support@evernorthstar.app</a>.
        We respond within 30 days.
      </p>
      <p>
        <strong>California residents:</strong> we do not sell or share personal
        information as those terms are defined under the California Consumer
        Privacy Act (CCPA/CPRA).
      </p>

      <h2>6. Security</h2>
      <ul>
        <li>All traffic to and from the Service is encrypted in transit via TLS 1.2+.</li>
        <li>Brokerage access tokens are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256) with a key derived from a server-side secret never stored alongside the data.</li>
        <li>User passwords are hashed with bcrypt before storage.</li>
        <li>Admin access to production infrastructure is restricted to the founder and requires multi-factor authentication.</li>
      </ul>
      <p>
        No system is perfectly secure. If you believe your account has been
        compromised, contact us immediately so we can revoke sessions and
        investigate.
      </p>

      <h2>7. Children</h2>
      <p>
        The Service is not directed to children under 13, and we do not
        knowingly collect personal information from anyone under 13. If you
        believe a child has provided us information, contact us and we will
        delete it.
      </p>

      <h2>8. Changes to this policy</h2>
      <p>
        We will post material changes to this Policy at least 14 days before
        they take effect, with a notice via email or in-product banner. The
        &quot;Effective date&quot; at the top of this page reflects the most recent
        revision.
      </p>

      <h2>9. Contact</h2>
      <p>
        Privacy questions or requests: email
        <a href="mailto:support@evernorthstar.app"> support@evernorthstar.app</a>.
        For our mailing address, request it via email.
      </p>
    </LegalPage>
  );
}
