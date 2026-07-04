"""Claude-written plain-English summary of a PositionPlan payload.

Renders the same underlying data as the PlanningCard UI but in prose,
suitable for the "Ask Claude to explain this position" button. Keeps the
legally-critical descriptive posture: no "buy," "sell," "should,"
"recommend." Language sticks to observation ("the zone is..."), history
("similar setups in the past have..."), and decision-framing ("you may
want to consider... vs...") — never prescription.
"""

from __future__ import annotations

import logging
from typing import Optional

from crypto_trends.ai import claude
from crypto_trends.portfolio.planning import PositionPlan

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are EverNorthstar's position planning writer.

Given a structured payload describing a user's position and its current
technical zone, write a 4-6 sentence plain-English summary. Style:
direct, calm, factual.

CRITICAL — NEVER use these words or their close synonyms in your output:
  "buy", "sell", "should", "recommend", "advise", "suggest you", "we
  think", "target price", "action to take"

INSTEAD, use descriptive framing:
  "the current zone is..."
  "similar setups in the past have..."
  "the framework surfaces the following ring-fence options..."
  "at this position size and cost basis, locking X% of gains would..."
  "you may want to weigh..." (never followed by a specific action)

Always end with an honest caveat about what the data doesn't show
(short window, thin sample, backward-looking only, etc).

You are describing data. The user decides what to do with it.
"""


def _format_plan(plan: PositionPlan) -> str:
    lines: list[str] = []
    lines.append(f"Ticker: {plan.base} ({plan.asset_class})")
    lines.append(f"Quantity: {plan.quantity}")
    if plan.cost_basis_per_share:
        lines.append(f"Cost basis per unit: ${plan.cost_basis_per_share:,.2f}")
    if plan.current_price:
        lines.append(f"Current price: ${plan.current_price:,.2f}")
    if plan.current_value:
        lines.append(f"Current value: ${plan.current_value:,.2f}")
    if plan.unrealized_gain_usd is not None and plan.unrealized_gain_pct is not None:
        lines.append(
            f"Unrealized: ${plan.unrealized_gain_usd:,.2f} "
            f"({plan.unrealized_gain_pct:+.1f}%)"
        )
    lines.append("")

    z = plan.zone
    lines.append(f"CURRENT ZONE: {z.zone} (confidence {z.zone_confidence:.2f})")
    if z.rsi is not None:
        lines.append(f"  RSI (14-day, Wilder): {z.rsi:.1f}")
    if z.bb_position_sigma is not None:
        lines.append(
            f"  Bollinger position: {z.bb_position_sigma:+.2f}σ from 20-day mean"
        )
    if z.score_percentile is not None:
        lines.append(
            f"  Momentum score percentile (90d): {z.score_percentile * 100:.0f}"
        )
    if z.volume_divergence:
        lines.append("  Volume divergence: yes — price and volume drifting opposite ways")
    if z.distribution_low is not None and z.distribution_high is not None:
        lines.append(
            f"  Distribution band: ${z.distribution_low:,.2f} .. ${z.distribution_high:,.2f}"
        )
    if z.accumulation_low is not None and z.accumulation_high is not None:
        lines.append(
            f"  Accumulation band: ${z.accumulation_low:,.2f} .. ${z.accumulation_high:,.2f}"
        )
    lines.append("")

    if plan.ring_fence_scenarios:
        lines.append("RING-FENCE OPTIONS (25% / 50% / 75% of unrealized gain locked):")
        for s in plan.ring_fence_scenarios:
            worst_case = "profit locked" if s.net_pl_if_remainder_zero_usd >= 0 else "still net-down"
            lines.append(
                f"  Lock {s.pct_of_gain_locked * 100:.0f}%: take ${s.amount_to_take_usd:,.0f}, "
                f"keep ${s.remaining_position_value:,.0f} at risk, "
                f"worst-case net {'$' if s.net_pl_if_remainder_zero_usd >= 0 else '-$'}"
                f"{abs(s.net_pl_if_remainder_zero_usd):,.0f} ({worst_case})"
            )
        lines.append("")

    if plan.historical and plan.historical.n_setups > 0:
        h = plan.historical
        lines.append(
            f"HISTORICAL CONTEXT (n={h.n_setups} similar prior setups, 2-year window):"
        )
        if h.median_fwd_30d_return_pct is not None:
            lines.append(f"  Median 30-day forward return: {h.median_fwd_30d_return_pct:+.1f}%")
        if h.p25_fwd_30d_return_pct is not None and h.p75_fwd_30d_return_pct is not None:
            lines.append(
                f"  Interquartile 30-day range: "
                f"{h.p25_fwd_30d_return_pct:+.1f}% .. {h.p75_fwd_30d_return_pct:+.1f}%"
            )
        if h.median_fwd_90d_return_pct is not None:
            lines.append(f"  Median 90-day forward return: {h.median_fwd_90d_return_pct:+.1f}%")
    return "\n".join(lines)


def summarize_plan(plan: PositionPlan) -> Optional[str]:
    """Returns a 4-6 sentence summary of the position plan, or None if AI
    is disabled or the data is too thin to be worth summarizing."""
    if not claude.is_enabled():
        return None
    # Skip trivial cases: no price data means nothing meaningful to say
    if plan.current_price is None:
        return None
    context = _format_plan(plan)
    user_prompt = (
        f"Summarize this position plan in 4-6 sentences using the rules in "
        f"your system prompt. Descriptive language only.\n\n{context}"
    )
    return claude.ask(SYSTEM_PROMPT, user_prompt, max_tokens=500)
