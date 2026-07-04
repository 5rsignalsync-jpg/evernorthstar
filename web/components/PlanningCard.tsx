"use client";

import { useCallback, useEffect, useState } from "react";
import {
  armHoldingPlan,
  fetchHoldingPlan,
  fetchSymbolPlan,
  type ArmPlanResult,
  type PositionPlan,
  type ZoneName,
} from "@/lib/api";

/**
 * Position planning card — the Merlin-style feature.
 *
 * Renders a data-descriptive view of a position: current zone, entry/exit
 * bands, ring-fence-of-gains scenarios, historical outcome distribution.
 * All copy is descriptive (never prescriptive) to stay inside the publisher
 * exemption. See /legal/disclaimer for the full framing.
 */

const ZONE_STYLES: Record<
  ZoneName,
  { label: string; color: string; border: string; bg: string }
> = {
  accumulation: {
    label: "Accumulation zone",
    color: "text-emerald-300",
    border: "border-emerald-500/40",
    bg: "bg-emerald-500/5",
  },
  neutral: {
    label: "Neutral",
    color: "text-zinc-300",
    border: "border-zinc-700",
    bg: "bg-zinc-800/30",
  },
  distribution: {
    label: "Distribution zone",
    color: "text-amber-300",
    border: "border-amber-500/40",
    bg: "bg-amber-500/5",
  },
  extreme_distribution: {
    label: "Extreme distribution",
    color: "text-rose-300",
    border: "border-rose-500/40",
    bg: "bg-rose-500/5",
  },
};

function fmtUSD(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !isFinite(v)) return "—";
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: digits,
  });
}

function fmtPct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !isFinite(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function PlanningCard({
  holdingId,
  symbol,
  quantity,
  costBasisPerShare,
}: {
  holdingId?: number;
  symbol?: string;
  quantity?: number;
  costBasisPerShare?: number;
}) {
  const [plan, setPlan] = useState<PositionPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [arming, setArming] = useState(false);
  const [armResult, setArmResult] = useState<ArmPlanResult | null>(null);
  const [armError, setArmError] = useState<string | null>(null);

  const handleArm = useCallback(async () => {
    if (!holdingId) return;
    setArming(true);
    setArmError(null);
    try {
      setArmResult(await armHoldingPlan(holdingId));
    } catch (e) {
      setArmError(e instanceof Error ? e.message : String(e));
    } finally {
      setArming(false);
    }
  }, [holdingId]);

  const loadPlan = useCallback(
    async (withAi: boolean) => {
      const setLoadingFlag = withAi ? setAiLoading : setLoading;
      setLoadingFlag(true);
      setError(null);
      try {
        const p = holdingId
          ? await fetchHoldingPlan(holdingId, { withAi })
          : symbol
            ? await fetchSymbolPlan(symbol, {
                quantity,
                costBasisPerShare,
                withAi,
              })
            : Promise.reject(new Error("Need holdingId or symbol"));
        setPlan(await Promise.resolve(p));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoadingFlag(false);
      }
    },
    [holdingId, symbol, quantity, costBasisPerShare],
  );

  useEffect(() => {
    void loadPlan(false);
  }, [loadPlan]);

  if (loading) {
    return (
      <div className="rounded-md border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-500">
        Building your position plan…
      </div>
    );
  }
  if (error) {
    return (
      <div className="rounded-md border border-rose-700/40 bg-rose-900/20 p-3 text-sm text-rose-200">
        {error}
      </div>
    );
  }
  if (!plan) return null;

  const z = plan.zone;
  const zoneStyle = ZONE_STYLES[z.zone];
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/40 p-4 space-y-4">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-base font-semibold text-zinc-100">
            📊 Position plan · {plan.base}
          </h3>
          <p className="text-[11px] text-zinc-500 mt-0.5">
            Data-descriptive planning tool. Not investment advice.
          </p>
        </div>
        <div className="text-right text-xs">
          <p className="text-zinc-500">Current price</p>
          <p className="text-zinc-100 font-medium tabular-nums">
            {fmtUSD(plan.current_price)}
          </p>
        </div>
      </div>

      {/* Zone banner */}
      <div className={`rounded p-3 border ${zoneStyle.border} ${zoneStyle.bg}`}>
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <div>
            <p className={`text-sm font-semibold ${zoneStyle.color}`}>
              {zoneStyle.label}
            </p>
            <p className="text-[11px] text-zinc-400 mt-0.5">
              Confidence: {(z.zone_confidence * 100).toFixed(0)}% ·
              {z.rsi !== null && <> RSI {z.rsi.toFixed(0)} ·</>}
              {z.bb_position_sigma !== null && (
                <> BB {z.bb_position_sigma >= 0 ? "+" : ""}
                  {z.bb_position_sigma.toFixed(1)}σ ·</>
              )}
              {z.score_percentile !== null && (
                <> Score {(z.score_percentile * 100).toFixed(0)}th %ile</>
              )}
              {z.volume_divergence && <> · volume divergence</>}
            </p>
          </div>
          {(z.accumulation_low || z.distribution_high) && (
            <div className="text-[11px] text-right space-y-0.5">
              {z.distribution_low && z.distribution_high && (
                <p className="text-amber-300 tabular-nums">
                  ▲ distribution: {fmtUSD(z.distribution_low)} .. {fmtUSD(z.distribution_high)}
                </p>
              )}
              {z.accumulation_low && z.accumulation_high && (
                <p className="text-emerald-300 tabular-nums">
                  ▼ accumulation: {fmtUSD(z.accumulation_low)} .. {fmtUSD(z.accumulation_high)}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Position metrics */}
      {plan.cost_basis_per_share !== null && plan.current_value !== null && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <Metric label="Quantity" value={plan.quantity.toString()} />
          <Metric
            label="Cost basis / unit"
            value={fmtUSD(plan.cost_basis_per_share)}
          />
          <Metric label="Current value" value={fmtUSD(plan.current_value)} />
          <Metric
            label="Unrealized"
            value={fmtUSD(plan.unrealized_gain_usd)}
            sub={fmtPct(plan.unrealized_gain_pct)}
            color={
              (plan.unrealized_gain_usd ?? 0) >= 0
                ? "text-emerald-300"
                : "text-rose-300"
            }
          />
        </div>
      )}

      {/* Ring-fence scenarios */}
      {plan.ring_fence_scenarios.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider mb-2">
            💰 Profit-taking framework
          </h4>
          <p className="text-[11px] text-zinc-500 mb-2">
            Ring-fence scenarios based on your unrealized gain of{" "}
            <span className="text-emerald-300 tabular-nums">
              {fmtUSD(plan.unrealized_gain_usd)}
            </span>
            . Data only — you decide.
          </p>
          <div className="rounded border border-zinc-800 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-zinc-900/60 text-[10px] text-zinc-500 uppercase tracking-wider">
                <tr>
                  <th className="text-left px-3 py-2">Lock</th>
                  <th className="text-right px-3 py-2">Take</th>
                  <th className="text-right px-3 py-2">Keep at risk</th>
                  <th className="text-right px-3 py-2" title="Net PL if remainder went to zero">
                    Worst-case net
                  </th>
                </tr>
              </thead>
              <tbody>
                {plan.ring_fence_scenarios.map((s) => (
                  <tr
                    key={s.pct_of_gain_locked}
                    className="border-t border-zinc-800/60"
                  >
                    <td className="px-3 py-2 text-zinc-100 font-medium">
                      {(s.pct_of_gain_locked * 100).toFixed(0)}% of gain
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-emerald-300">
                      {fmtUSD(s.amount_to_take_usd)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-zinc-300">
                      {fmtUSD(s.remaining_position_value)}
                    </td>
                    <td
                      className={`px-3 py-2 text-right tabular-nums ${
                        s.net_pl_if_remainder_zero_usd >= 0
                          ? "text-emerald-300"
                          : "text-zinc-400"
                      }`}
                    >
                      {fmtUSD(s.net_pl_if_remainder_zero_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Entry ladder */}
      {plan.entry_plan && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider mb-2">
            🪜 Accumulation-zone ladder
          </h4>
          <p className="text-[11px] text-zinc-500 mb-2">
            Status: <span className="text-zinc-300">{plan.entry_plan.status.replace("_", " ")}</span>{" "}
            · Band ${plan.entry_plan.accumulation_low.toFixed(2)} .. $
            {plan.entry_plan.accumulation_high.toFixed(2)} · Invalidation $
            {plan.entry_plan.invalidation_level.toFixed(2)}
          </p>
          <div className="rounded border border-zinc-800 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-zinc-900/60 text-[10px] text-zinc-500 uppercase tracking-wider">
                <tr>
                  <th className="text-left px-3 py-2">Rung</th>
                  <th className="text-right px-3 py-2">Price</th>
                  <th className="text-right px-3 py-2">% of budget</th>
                </tr>
              </thead>
              <tbody>
                {plan.entry_plan.tranches.map((t) => (
                  <tr key={t.label} className="border-t border-zinc-800/60">
                    <td className="px-3 py-2 text-zinc-100 font-medium capitalize">
                      {t.label}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-zinc-200">
                      {fmtUSD(t.price)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-zinc-300">
                      {(t.pct_of_budget * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-zinc-600 leading-relaxed mt-1.5">
            {plan.entry_plan.note}
          </p>
          {holdingId && (
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <button
                onClick={() => void handleArm()}
                disabled={arming}
                className="text-xs font-medium rounded bg-emerald-600/90 hover:bg-emerald-600 text-white px-3 py-1.5 disabled:opacity-60"
                title="Set price alerts at every entry rung, the invalidation, and the take-profit zone"
              >
                {arming
                  ? "Arming…"
                  : armResult
                    ? "↻ Re-arm alerts"
                    : "🔔 Arm this plan"}
              </button>
              {armResult && (
                <span className="text-[11px] text-emerald-300">
                  ✓ Armed {armResult.armed} alert
                  {armResult.armed === 1 ? "" : "s"}
                  {armResult.replaced > 0
                    ? ` (replaced ${armResult.replaced})`
                    : ""}
                </span>
              )}
              {armError && (
                <span className="text-[11px] text-rose-300">{armError}</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Historical outcomes */}
      {plan.historical && plan.historical.n_setups >= 3 && (
        <div>
          <h4 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider mb-2">
            📉 Historical context
          </h4>
          <p className="text-[11px] text-zinc-500 mb-2">
            In the last 2 years, this ticker was in the <em>{zoneStyle.label.toLowerCase()}</em>{" "}
            {plan.historical.n_setups} times. Here is what happened afterward.
            These describe the past — they do not predict the future.
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <StatBox
              label="Median 30d return"
              value={fmtPct(plan.historical.median_fwd_30d_return_pct, 1)}
              color={
                (plan.historical.median_fwd_30d_return_pct ?? 0) >= 0
                  ? "text-emerald-300"
                  : "text-rose-300"
              }
            />
            <StatBox
              label="Median 90d return"
              value={fmtPct(plan.historical.median_fwd_90d_return_pct, 1)}
              color={
                (plan.historical.median_fwd_90d_return_pct ?? 0) >= 0
                  ? "text-emerald-300"
                  : "text-rose-300"
              }
            />
            <StatBox
              label="25th %ile 30d"
              value={fmtPct(plan.historical.p25_fwd_30d_return_pct, 1)}
            />
            <StatBox
              label="75th %ile 30d"
              value={fmtPct(plan.historical.p75_fwd_30d_return_pct, 1)}
            />
          </div>

          {plan.historical.sample.length > 0 && (
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-zinc-400 hover:text-zinc-200 select-none list-none">
                Show {plan.historical.sample.length} similar past setups ▾
              </summary>
              <div className="mt-2 rounded border border-zinc-800 overflow-hidden">
                <table className="w-full text-[11px]">
                  <thead className="bg-zinc-900/60 text-[10px] text-zinc-500 uppercase tracking-wider">
                    <tr>
                      <th className="text-left px-3 py-1.5">Date</th>
                      <th className="text-right px-3 py-1.5">Setup price</th>
                      <th className="text-right px-3 py-1.5">Fwd 30d</th>
                      <th className="text-right px-3 py-1.5">Fwd 90d</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.historical.sample.map((o) => (
                      <tr
                        key={o.setup_date}
                        className="border-t border-zinc-800/60"
                      >
                        <td className="px-3 py-1.5 text-zinc-300">
                          {o.setup_date}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums text-zinc-200">
                          {fmtUSD(o.setup_price)}
                        </td>
                        <td
                          className={
                            "px-3 py-1.5 text-right tabular-nums " +
                            ((o.fwd_30d_return_pct ?? 0) >= 0
                              ? "text-emerald-300"
                              : "text-rose-300")
                          }
                        >
                          {fmtPct(o.fwd_30d_return_pct, 1)}
                        </td>
                        <td
                          className={
                            "px-3 py-1.5 text-right tabular-nums " +
                            ((o.fwd_90d_return_pct ?? 0) >= 0
                              ? "text-emerald-300"
                              : "text-rose-300")
                          }
                        >
                          {fmtPct(o.fwd_90d_return_pct, 1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </div>
      )}

      {/* AI summary */}
      {plan.ai_enabled && (
        <div className="rounded-md border border-purple-600/40 bg-purple-500/5 p-3">
          <div className="flex items-baseline justify-between gap-3 flex-wrap">
            <h4 className="text-xs font-semibold text-purple-200 uppercase tracking-wider">
              🤖 Claude read your plan
            </h4>
            <button
              type="button"
              onClick={() => void loadPlan(true)}
              disabled={aiLoading}
              className="text-[11px] rounded bg-purple-600/30 border border-purple-500/50 px-2.5 py-1 text-purple-100 hover:bg-purple-600/50 disabled:opacity-50"
            >
              {aiLoading
                ? "Thinking…"
                : plan.ai_summary
                  ? "Re-summarize"
                  : "Summarize this position"}
            </button>
          </div>
          {plan.ai_summary && (
            <p className="text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap mt-3">
              {plan.ai_summary}
            </p>
          )}
        </div>
      )}

      <p className="text-[10px] text-zinc-600 leading-relaxed border-t border-zinc-800 pt-3">
        {plan.disclaimer}
      </p>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 px-2.5 py-2">
      <p className="text-[10px] text-zinc-500 uppercase tracking-wider">
        {label}
      </p>
      <p
        className={`text-sm font-medium tabular-nums mt-1 ${
          color ?? "text-zinc-100"
        }`}
      >
        {value}
      </p>
      {sub && (
        <p className="text-[10px] text-zinc-500 tabular-nums">{sub}</p>
      )}
    </div>
  );
}

function StatBox({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 px-3 py-2">
      <p className="text-[10px] text-zinc-500 uppercase tracking-wider">
        {label}
      </p>
      <p
        className={`text-sm font-semibold tabular-nums mt-1 ${
          color ?? "text-zinc-200"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
