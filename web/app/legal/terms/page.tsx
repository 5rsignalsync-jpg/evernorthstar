import { LegalPage } from "@/components/LegalPage";

export const metadata = {
  title: "Terms of Service · EverNorthstar",
  description: "The terms governing your use of EverNorthstar.",
};

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" effectiveDate="2026-06-18">
      <h2>1. Acceptance of these terms</h2>
      <p>
        By creating an account at evernorthstar.app or otherwise using
        EverNorthstar (the &quot;Service&quot;), you agree to these Terms of Service
        (the &quot;Terms&quot;). If you do not agree, do not use the Service.
        EverNorthstar is operated by 5Royals Investments LLC, a Wyoming
        limited liability company with its principal place of business in
        Colorado (&quot;we,&quot; &quot;us,&quot; or &quot;EverNorthstar&quot;).
      </p>

      <h2>2. What EverNorthstar is</h2>
      <p>
        EverNorthstar is a research and analytics dashboard. We aggregate
        publicly-available data (price history, news, SEC Form 13F and Form 4
        filings, STOCK Act disclosures), score it with proprietary signals,
        and let you cross-reference your own brokerage holdings against those
        signals via Plaid.
      </p>
      <p>
        <strong>EverNorthstar is not a broker-dealer, investment adviser,
        financial planner, accountant, tax advisor, or fiduciary.</strong> We
        do not execute trades, hold customer funds or securities, or provide
        personalized investment advice. Everything we show you is general
        market information.
      </p>

      <h2>3. Eligibility</h2>
      <p>
        You must be at least 18 years old and legally able to enter contracts
        in your jurisdiction. The Service is currently offered only to users
        in the United States. By using it, you represent that you meet these
        requirements.
      </p>

      <h2>4. Your account</h2>
      <p>
        You are responsible for keeping your login credentials confidential
        and for all activity on your account. Notify us immediately at
        <a href="mailto:support@evernorthstar.app"> support@evernorthstar.app</a> if
        you suspect unauthorized access. You agree not to share, sell, or
        sublicense your account.
      </p>

      <h2>5. Subscriptions, billing, and cancellation</h2>
      <p>
        Paid plans (Pro monthly, Pro annual, Founder Lifetime) are billed
        through Stripe. By providing a payment method you authorize us to
        charge the listed price for the selected billing period, including
        applicable taxes.
      </p>
      <ul>
        <li>
          Pro monthly and Pro annual subscriptions renew automatically until
          cancelled.
        </li>
        <li>
          You can cancel anytime from Account → Manage Billing. Cancellation
          takes effect at the end of the current billing period; you keep Pro
          access until then.
        </li>
        <li>
          Founder Lifetime is a one-time payment that grants Pro-tier access
          for the life of the Service. It is non-renewing and non-transferable.
        </li>
        <li>
          We may change prices for future renewal periods with at least 30
          days notice via email.
        </li>
      </ul>

      <h2>6. Refunds</h2>
      <p>
        Refund eligibility is described in our
        <a href="/legal/refunds"> Refund Policy</a>. The short version: we
        offer a 7-day refund on your first charge, no questions asked.
        Founder Lifetime purchases follow the same 7-day window.
      </p>

      <h2>7. Brokerage data via Plaid</h2>
      <p>
        If you choose to connect a brokerage account, you authorize EverNorthstar
        to use Plaid Inc. to retrieve read-only holdings data on your behalf.
        We never see, store, or transmit your brokerage username, password, or
        two-factor codes. Plaid&apos;s handling of your credentials is governed
        by their <a href="https://plaid.com/legal/" target="_blank" rel="noopener noreferrer">end-user privacy policy</a>.
      </p>
      <p>
        Your access token (issued by Plaid) is stored encrypted at rest on our
        servers using AES-128-CBC with HMAC-SHA256 via the Fernet scheme. We
        only have permission to read holdings — we cannot initiate trades or
        transfer money on your behalf.
      </p>

      <h2>8. Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>Reverse-engineer, scrape, or republish our signals or data feeds.</li>
        <li>Resell or redistribute the Service or its outputs to third parties without our written consent.</li>
        <li>Use the Service to violate any law or harm anyone else.</li>
        <li>Attempt to circumvent rate limits, access controls, or paid-tier gating.</li>
        <li>Upload malicious code, run automated bots, or interfere with the Service&apos;s operation.</li>
      </ul>
      <p>
        We may suspend or terminate accounts that violate these rules,
        with or without notice.
      </p>

      <h2>9. Intellectual property</h2>
      <p>
        The Service, including its source code, designs, signal methodologies,
        documentation, and the EverNorthstar name and star logo, is owned by
        5Royals Investments LLC or its licensors. We grant you a limited,
        non-exclusive, revocable license to use the Service for your personal,
        non-commercial research. All other rights are reserved.
      </p>

      <h2>10. Disclaimers and limitation of liability</h2>
      <p>
        <strong>The Service is provided &quot;as is&quot; without warranties of any
        kind.</strong> We do not warrant that signals are accurate, that any
        strategy will be profitable, or that the Service will be uninterrupted.
        See our <a href="/legal/disclaimer">Financial Disclaimer</a> for the
        full disclosure.
      </p>
      <p>
        To the maximum extent permitted by law, our total liability for any
        claim arising out of or relating to the Service is limited to the
        amount you have paid us in the 12 months preceding the claim. We are
        not liable for indirect, incidental, consequential, or punitive
        damages, including lost profits or trading losses, even if we have
        been advised of the possibility of such damages.
      </p>

      <h2>11. Indemnification</h2>
      <p>
        You agree to indemnify and hold harmless 5Royals Investments LLC, its
        officers, contractors, and affiliates from any claim, loss, or expense
        (including reasonable attorneys&apos; fees) arising out of your use of
        the Service, your breach of these Terms, or your violation of any
        third-party rights.
      </p>

      <h2>12. Termination</h2>
      <p>
        You may stop using the Service and delete your account at any time. We
        may suspend or terminate your access if you breach these Terms or if
        we discontinue the Service. Sections that by their nature should
        survive termination (intellectual property, disclaimers, limitation of
        liability, indemnification, governing law) will survive.
      </p>

      <h2>13. Changes to the Service or these Terms</h2>
      <p>
        We may update the Service and these Terms from time to time. Material
        changes will be communicated by email or via an in-product notice at
        least 14 days before they take effect. Continued use after the
        effective date constitutes acceptance.
      </p>

      <h2>14. Governing law and disputes</h2>
      <p>
        These Terms are governed by the laws of the State of Wyoming (the
        state in which 5Royals Investments LLC is organized), without regard
        to its conflict-of-laws principles. Any dispute will be resolved in
        the state or federal courts located in Denver County, Colorado (the
        county of our principal place of business), and you consent to
        personal jurisdiction there. You and we waive any right to a jury
        trial. Disputes must be brought individually, not as a class action.
      </p>

      <h2>15. Contact</h2>
      <p>
        Questions about these Terms? Email
        <a href="mailto:support@evernorthstar.app"> support@evernorthstar.app</a>.
      </p>
    </LegalPage>
  );
}
