import { LegalPage } from "@/components/LegalPage";

export const metadata = {
  title: "Refund Policy · EverNorthstar",
  description: "When you can get a refund from EverNorthstar, and how to request one.",
};

export default function RefundsPage() {
  return (
    <LegalPage title="Refund Policy" effectiveDate="2026-06-18">
      <p>
        We want you to feel comfortable trying EverNorthstar. Here&apos;s when
        you can get your money back and how to ask.
      </p>

      <h2>The short version</h2>
      <ul>
        <li><strong>First-charge refund window:</strong> 7 days, no questions asked.</li>
        <li><strong>Founder Lifetime:</strong> same 7-day window from the day of purchase.</li>
        <li><strong>Recurring renewals:</strong> not refundable, but you can cancel anytime to stop future charges.</li>
        <li><strong>Crypto payments via NOWPayments:</strong> generally non-refundable due to blockchain irreversibility, but contact us — we&apos;ll work something out.</li>
      </ul>

      <h2>1. First-charge refund (Pro monthly, Pro annual, Founder Lifetime)</h2>
      <p>
        If you are unhappy with EverNorthstar for any reason within{" "}
        <strong>7 days</strong> of your first charge, email{" "}
        <a href="mailto:support@evernorthstar.app">support@evernorthstar.app</a>{" "}
        from the email address on your account with the subject line
        &quot;Refund request.&quot; We will issue a full refund to your original
        payment method within 5 business days. No questions, no hoops.
      </p>
      <p>
        This applies to your very first charge only, not to subsequent
        renewals or upgrades.
      </p>

      <h2>2. Subsequent renewals (Pro monthly and Pro annual)</h2>
      <p>
        After the 7-day window, monthly and annual subscription renewals are
        generally non-refundable. You can cancel at any time from Account →
        Manage Billing; you keep Pro access until the end of the current
        billing period, and you will not be charged again.
      </p>
      <p>
        If a renewal posted because of a technical failure on our end (e.g.,
        you cancelled but our system charged you anyway), email us and we
        will refund it immediately.
      </p>

      <h2>3. Annual plan, mid-term cancellation</h2>
      <p>
        If you purchased an annual plan, you can cancel at any time from
        Account → Manage Billing. After the initial 7-day window, we do not
        prorate refunds for the unused portion of the year. You keep Pro
        access through the end of the paid term.
      </p>

      <h2>4. Founder Lifetime</h2>
      <p>
        Founder Lifetime is a one-time purchase that grants Pro access for
        the life of the Service. It is eligible for our standard 7-day refund
        from the date of purchase. After 7 days it is non-refundable.
      </p>
      <p>
        If EverNorthstar is permanently shut down within 24 months of your
        Founder Lifetime purchase, we will refund a pro-rated amount based
        on a 24-month amortization. (For example, a shutdown after 12 months
        would return 50% of the $99 purchase price.)
      </p>

      <h2>5. Crypto payments (NOWPayments)</h2>
      <p>
        Crypto transactions are typically irreversible on the blockchain. If
        you paid in crypto and want a refund within the 7-day window, email
        us — we will refund the equivalent USD value back to a wallet
        address you control. Network fees for the refund transaction are
        deducted from the refunded amount.
      </p>

      <h2>6. How to request a refund</h2>
      <p>Email <a href="mailto:support@evernorthstar.app">support@evernorthstar.app</a> from the email on your account with:</p>
      <ul>
        <li>Subject: &quot;Refund request&quot;</li>
        <li>Approximate date of purchase</li>
        <li>(Optional) A sentence on why — helps us improve, never required</li>
      </ul>
      <p>
        We respond within 1 business day and process approved refunds within
        5 business days. Stripe refunds typically appear on your card within
        5-10 business days depending on your bank.
      </p>

      <h2>7. Chargebacks</h2>
      <p>
        If you have a billing concern, please email us first — we will almost
        always resolve it faster than a chargeback. Disputed chargebacks
        without prior contact may result in account suspension while we
        investigate.
      </p>
    </LegalPage>
  );
}
