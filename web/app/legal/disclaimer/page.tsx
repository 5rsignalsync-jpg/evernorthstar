import { LegalPage } from "@/components/LegalPage";

export const metadata = {
  title: "Financial Disclaimer · EverNorthstar",
  description: "What EverNorthstar's signals are, what they are not, and how to think about them honestly.",
};

export default function DisclaimerPage() {
  return (
    <LegalPage title="Financial Disclaimer" effectiveDate="2026-06-18">
      <p>
        We&apos;ve put this disclaimer on its own page because it matters. Read
        it carefully before acting on anything you see in EverNorthstar.
      </p>

      <h2>1. EverNorthstar is not your financial advisor</h2>
      <p>
        EverNorthstar is a research and analytics tool. We are{" "}
        <strong>not</strong>:
      </p>
      <ul>
        <li>A registered investment adviser (RIA) under the Investment Advisers Act of 1940.</li>
        <li>A broker-dealer registered with FINRA.</li>
        <li>A commodity pool operator or commodity trading advisor.</li>
        <li>A bank, trust company, or other regulated financial institution.</li>
        <li>A fiduciary, financial planner, or accountant for any user.</li>
      </ul>
      <p>
        Nothing on this site, in our emails, or in our AI-generated summaries
        constitutes personalized investment advice, an offer to buy or sell
        any security, or a solicitation to enter into any transaction. We do
        not know your full financial situation, time horizon, tax bracket,
        risk tolerance, dependents, debts, or goals — and we make no effort to.
      </p>

      <h2>2. What our signals actually are</h2>
      <p>
        Our momentum and long-term signals are statistical scores computed
        from publicly-available price and fundamentals data. They reflect
        recent relative-strength patterns and quality/value factors compared
        to other names in the same universe. <strong>They do not predict
        future returns.</strong> A high score does not mean a stock will go up.
        A low score does not mean a stock will go down.
      </p>
      <p>
        Our smart-money strategies (Burry Bets, Buffett Watcher, Pelosi
        Tracker, etc.) display the publicly-disclosed positions of named
        investors. Those disclosures are <strong>lagged</strong> — 13F filings
        appear up to 45 days after the quarter ends, Congressional trades up
        to 45 days after execution. By the time you see them, the disclosed
        investor may have already exited the position. We surface this lag
        prominently on every strategy view.
      </p>

      <h2>3. Past performance does not predict future results</h2>
      <p>
        Backtested return figures shown on strategy cards represent the
        weighted return of currently-disclosed positions since the most-recent
        disclosure date, computed from public price history. Real-world
        trading results will differ because:
      </p>
      <ul>
        <li>Disclosed holdings are a snapshot — the actor&apos;s actual current portfolio differs.</li>
        <li>You incur bid-ask spreads, commissions, slippage, and taxes that backtests don&apos;t capture.</li>
        <li>Survivorship bias affects historical universes.</li>
        <li>Past disclosures don&apos;t obligate the disclosed actor to maintain or repeat the position.</li>
      </ul>

      <h2>4. AI-generated content is best-effort</h2>
      <p>
        The Ask Why button, Daily Digest email, and Earnings Recap feature
        use Anthropic&apos;s Claude language model to synthesize publicly-available
        data into plain-English summaries. These summaries may contain errors,
        omissions, or misinterpretations. Treat them as a starting point for
        your own research, not as authoritative analysis. We do not guarantee
        their accuracy.
      </p>

      <h2>5. Smart-money tracking is not insider trading</h2>
      <p>
        All smart-money data we surface comes from <strong>mandatory public
        disclosures</strong> — SEC Form 13F (institutional managers with $100M+
        AUM), SEC Form 4 (corporate insiders), and the STOCK Act (members of
        Congress and senior staffers). These are publicly searchable on SEC
        EDGAR, the House and Senate disclosure portals, and elsewhere. We
        aggregate and present them; we do not solicit or process material
        non-public information.
      </p>

      <h2>6. Crypto carries unique risks</h2>
      <p>
        Our crypto and crypto-micro sleeves cover digital assets that are
        often unregulated, highly volatile, susceptible to manipulation, and
        in many cases subject to total loss. Past price action is especially
        unreliable in crypto. Consider these positions speculative.
      </p>

      <h2>7. You assume all risk</h2>
      <p>
        <strong>All investment and trading decisions are yours alone.</strong> You
        bear sole responsibility for the consequences of those decisions,
        including any financial loss. You should consult a licensed financial
        advisor, tax professional, and attorney before making material
        financial decisions based on anything you read on EverNorthstar.
      </p>

      <h2>8. Limitation of liability</h2>
      <p>
        To the maximum extent permitted by law, 5Royals Investments LLC, its
        officers, contractors, and affiliates are not liable for any
        investment loss, tax liability, missed opportunity, or other damage
        arising out of your use of the Service or your reliance on any
        information it provides. See our
        <a href="/legal/terms"> Terms of Service</a> for the full liability
        framework.
      </p>
    </LegalPage>
  );
}
