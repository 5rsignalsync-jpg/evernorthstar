"use client";

import { useEffect, useState } from "react";
import {
  fetchActorBasket,
  fetchSmartMoneyActors,
  fetchSmartMoneyLeaders,
  fetchStrategies,
  type ActorPosition,
  type ActorSummary,
  type SmartMoneyLeader,
  type SmartMoneyResponse,
  type StrategyCard,
} from "@/lib/api";
import { CardSkeleton, TableSkeleton } from "./Skeleton";
import { ProUpsell } from "./ProUpsell";
import { ScoreLegend } from "./ScoreLegend";
import { StarButton } from "./StarButton";
import { StrategyDetailModal } from "./StrategyDetailModal";

const POLL_INTERVAL_MS = 5 * 60_000; // smart-money data refreshes on its own slow cadence

function formatBillions(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function netColor(v: number): string {
  if (v > 1e6) return "text-emerald-400";
  if (v > 0) return "text-emerald-300";
  if (v < -1e6) return "text-rose-400";
  if (v < 0) return "text-rose-300";
  return "text-zinc-500";
}

function scoreColor(score: number): string {
  if (score > 0.5) return "text-emerald-400";
  if (score > 0.2) return "text-emerald-300";
  if (score < -0.5) return "text-rose-400";
  if (score < -0.2) return "text-rose-300";
  return "text-zinc-400";
}

export function SmartMoneyTab({
  onSelectSymbol,
}: {
  onSelectSymbol: (symbol: string) => void;
}) {
  const [data, setData] = useState<SmartMoneyResponse | null>(null);
  const [strategies, setStrategies] = useState<StrategyCard[] | null>(null);
  const [openStrategy, setOpenStrategy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [leaders, strats] = await Promise.all([
          fetchSmartMoneyLeaders(90, 25),
          fetchStrategies(),
        ]);
        if (!cancelled) {
          setData(leaders);
          setStrategies(strats);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="rounded-md border border-zinc-800 bg-zinc-900/40 px-4 py-3 text-[11px] text-zinc-400">
        <strong className="text-zinc-300">Data sources:</strong>{" "}
        13F filings (institutional positions, long-only equity book) ·
        Form 4 insider trades (10b5-1 programmed sales flagged) ·
        Congress trades from FMP. The aggregated leaderboard below blends all
        three into a single conviction score per ticker.
      </div>

      {error && (
        <div className="rounded-md border border-rose-700/40 bg-rose-900/20 px-4 py-3 text-sm text-rose-200">
          API error: {error}
        </div>
      )}

      {strategies && (
        <div>
          <h2 className="text-lg font-semibold text-zinc-100 mb-3">
            Curated strategies
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {strategies.map((s) => (
              <StrategyCardEl
                key={s.slug}
                card={s}
                onOpen={() => s.ready && setOpenStrategy(s.slug)}
              />
            ))}
          </div>
        </div>
      )}

      {!strategies && !error && (
        <div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 mb-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
            <TableSkeleton rows={5} />
          </div>
        </div>
      )}

      {data && (
        <>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-lg font-semibold text-zinc-100">
                Top-ranked tickers · smart_money_v1
              </h2>
              <span className="text-xs text-zinc-500">
                window: {data.window_days}d · {data.leaders.length} shown
              </span>
            </div>
            <ScoreLegend kind="smart_money" />
            <table className="w-full text-sm">
              <thead>
                <tr className="text-zinc-500 text-xs uppercase tracking-wider">
                  <th className="text-left font-normal py-2 w-6"></th>
                  <th className="text-left font-normal py-2 w-6">#</th>
                  <th className="text-left font-normal py-2">Ticker</th>
                  <th className="text-right font-normal py-2">Score</th>
                  <th className="text-right font-normal py-2"># 13F funds</th>
                  <th className="text-right font-normal py-2">13F value</th>
                  <th className="text-right font-normal py-2">Insider net</th>
                  <th className="text-left pl-4 font-normal py-2">Top actors</th>
                </tr>
              </thead>
              <tbody>
                {data.leaders.map((row, i) => (
                  <LeaderRow
                    key={row.ticker}
                    row={row}
                    index={i}
                    onClick={() => onSelectSymbol(row.ticker)}
                  />
                ))}
              </tbody>
            </table>
            {data.upsell_text && <ProUpsell text={data.upsell_text} variant="card" />}
          </div>

          <FollowInvestor />
        </>
      )}

      {openStrategy && (
        <StrategyDetailModal
          slug={openStrategy}
          onClose={() => setOpenStrategy(null)}
          onSelectSymbol={onSelectSymbol}
        />
      )}
    </div>
  );
}


function StrategyCardEl({
  card,
  onOpen,
}: {
  card: StrategyCard;
  onOpen: () => void;
}) {
  const cls = card.ready
    ? "border-zinc-700 bg-zinc-900/80 hover:bg-zinc-800/80 hover:border-zinc-600 cursor-pointer"
    : "border-zinc-800/60 bg-zinc-950/40 cursor-not-allowed opacity-70";

  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={!card.ready}
      className={`text-left rounded-lg border p-3 transition-colors ${cls}`}
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-base font-semibold text-zinc-100">
          {card.emoji} {card.name}
        </span>
        {card.ready ? (
          <span className="text-[10px] text-zinc-500">
            {card.n_positions} pos
          </span>
        ) : (
          <span className="text-[10px] px-1.5 py-0.5 rounded border border-amber-500/40 bg-amber-500/10 text-amber-300">
            GATED
          </span>
        )}
      </div>
      <p className="text-xs text-zinc-400 leading-snug line-clamp-3">
        {card.description}
      </p>
      {!card.ready && card.gated_reason && (
        <p className="text-[10px] text-amber-300/80 mt-2 leading-tight">
          {card.gated_reason}
        </p>
      )}
      {card.ready && card.last_activity && (
        <p className="text-[10px] text-zinc-600 mt-2">
          Last disclosure: {card.last_activity.slice(0, 10)}
        </p>
      )}
      {card.ready && card.performance && card.performance.tickers_priced > 0 && (
        <p
          className={
            "text-[10px] mt-1 font-medium " +
            (card.performance.strategy_return_pct >= 0
              ? "text-emerald-400"
              : "text-rose-400")
          }
          title={
            `If you'd bought this basket on ${card.performance.since}, ` +
            `holding for ${card.performance.days_held} days, weighted ` +
            `return on the ${card.performance.tickers_priced} positions we can price.`
          }
        >
          Since {card.performance.since}:{" "}
          {card.performance.strategy_return_pct >= 0 ? "+" : ""}
          {card.performance.strategy_return_pct.toFixed(2)}%
          <span className="text-zinc-600 font-normal">
            {" "}· {card.performance.days_held}d
          </span>
        </p>
      )}
    </button>
  );
}

function LeaderRow({
  row,
  index,
  onClick,
}: {
  row: SmartMoneyLeader;
  index: number;
  onClick: () => void;
}) {
  const topNames = row.top_actors.slice(0, 3).map((a) => a.actor_name).join(", ");
  return (
    <tr
      className="border-t border-zinc-800/60 cursor-pointer hover:bg-zinc-800/30"
      onClick={onClick}
      title="Click for chart + headlines"
    >
      <td className="py-2" onClick={(e) => e.stopPropagation()}>
        <StarButton symbol={row.ticker} asset_class="equity_large" base={row.ticker} />
      </td>
      <td className="py-2 text-zinc-500">{index + 1}</td>
      <td className="py-2 text-zinc-100 font-medium">{row.ticker}</td>
      <td className={`py-2 text-right tabular-nums font-medium ${scoreColor(row.score)}`}>
        {row.score >= 0 ? "+" : ""}
        {row.score.toFixed(3)}
      </td>
      <td className="py-2 text-right tabular-nums text-zinc-300">
        {row.n_funds_holding || "—"}
      </td>
      <td className="py-2 text-right tabular-nums text-zinc-300">
        {row.total_13f_value_usd > 0 ? formatBillions(row.total_13f_value_usd) : "—"}
      </td>
      <td className={`py-2 text-right tabular-nums ${netColor(row.insider_net_usd)}`}>
        {row.insider_net_usd === 0
          ? "—"
          : (row.insider_net_usd >= 0 ? "+" : "−") +
            formatBillions(Math.abs(row.insider_net_usd))}
      </td>
      <td className="py-2 pl-4 text-xs text-zinc-500 max-w-[220px] truncate">
        {topNames || "—"}
      </td>
    </tr>
  );
}

function FollowInvestor() {
  const [actors, setActors] = useState<ActorSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [basket, setBasket] = useState<ActorPosition[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSmartMoneyActors()
      .then(setActors)
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setBasket(null);
      return;
    }
    setBasket(null);
    fetchActorBasket(selectedId)
      .then((b) => setBasket(b.positions))
      .catch((e) => setError(String(e)));
  }, [selectedId]);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-zinc-100">Follow an investor</h2>
        <span className="text-xs text-zinc-500">
          {actors ? `${actors.length} tracked` : ""}
        </span>
      </div>

      {error && <p className="text-xs text-rose-300">{error}</p>}

      <select
        value={selectedId ?? ""}
        onChange={(e) => setSelectedId(e.target.value || null)}
        className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100 mb-3"
      >
        <option value="">Pick an actor…</option>
        {actors?.map((a) => (
          <option key={a.actor_id} value={a.actor_id}>
            {a.actor_name} · {a.source} · {a.n_trades} positions
          </option>
        ))}
      </select>

      {basket && (
        <div>
          <p className="text-[11px] text-zinc-500 mb-2">
            Aggregated positions (latest disclosure). 13F shows total $ value per
            holding; insider rows show transaction dollar values. Sort: largest first.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-zinc-500 text-xs uppercase tracking-wider">
                <th className="text-left font-normal py-2">Ticker</th>
                <th className="text-left font-normal py-2">Side</th>
                <th className="text-right font-normal py-2">Amount</th>
                <th className="text-right font-normal py-2">Shares</th>
                <th className="text-right font-normal py-2">As of</th>
              </tr>
            </thead>
            <tbody>
              {basket.slice(0, 25).map((p, i) => (
                <tr key={`${p.ticker}-${i}`} className="border-t border-zinc-800/60">
                  <td className="py-2 text-zinc-100 font-medium">{p.ticker}</td>
                  <td className={`py-2 ${p.side === "buy" ? "text-emerald-400" : "text-rose-300"}`}>
                    {p.side}
                  </td>
                  <td className="py-2 text-right tabular-nums text-zinc-300">
                    {p.amount_min ? formatBillions(p.amount_min) : "—"}
                  </td>
                  <td className="py-2 text-right tabular-nums text-zinc-300">
                    {p.shares ? p.shares.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}
                  </td>
                  <td className="py-2 text-right text-zinc-500 text-xs">
                    {p.last_disclosed ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {basket.length === 0 && (
            <p className="text-xs text-zinc-500 py-3">No positions to display.</p>
          )}
        </div>
      )}
    </div>
  );
}
