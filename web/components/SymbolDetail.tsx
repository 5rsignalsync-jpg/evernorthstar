"use client";

import { useEffect, useRef, useState } from "react";
import {
  AreaSeries,
  ColorType,
  createChart,
  type IChartApi,
  LineSeries,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  fetchAskWhy,
  fetchEarningsSummary,
  fetchSymbolDetail,
  fetchTickerDescription,
  type AskWhyResult,
  type EarningsSummaryResult,
  type SymbolDetail,
  type TickerDescription,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { PlanningCard } from "@/components/PlanningCard";

function fmtPrice(p: number): string {
  if (p < 0.01) return p.toFixed(6);
  if (p < 1) return p.toFixed(4);
  if (p < 100) return p.toFixed(2);
  return p.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function sentimentColor(s: number | null): string {
  if (s === null) return "text-zinc-500";
  if (s > 0.3) return "text-emerald-300";
  if (s > 0.05) return "text-emerald-400/70";
  if (s < -0.3) return "text-rose-300";
  if (s < -0.05) return "text-rose-400/70";
  return "text-zinc-400";
}

export function SymbolDetailModal({
  symbol,
  signal,
  onClose,
}: {
  symbol: string;
  signal: string;
  onClose: () => void;
}) {
  const { isPro } = useAuth();
  const [data, setData] = useState<SymbolDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [desc, setDesc] = useState<TickerDescription | null>(null);
  const [askResult, setAskResult] = useState<AskWhyResult | null>(null);
  const [askLoading, setAskLoading] = useState(false);
  const [earningsResult, setEarningsResult] = useState<EarningsSummaryResult | null>(null);
  const [earningsLoading, setEarningsLoading] = useState(false);
  const [showPlan, setShowPlan] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchSymbolDetail(symbol, 90, signal)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message ?? String(e)));
    return () => {
      cancelled = true;
    };
  }, [symbol, signal]);

  // Lazy-fetch a longer description from yfinance once we know what asset
  // class this is. Skipped silently if yfinance has nothing for this ticker.
  useEffect(() => {
    if (!data) return;
    let cancelled = false;
    fetchTickerDescription(data.base, data.asset_class)
      .then((d) => !cancelled && setDesc(d))
      .catch(() => {}); // silent — description is decorative, not critical
    return () => {
      cancelled = true;
    };
  }, [data]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const lastClose = data?.price_series.at(-1)?.close ?? null;
  const firstClose = data?.price_series[0]?.close ?? null;
  const pctChange =
    lastClose !== null && firstClose !== null && firstClose !== 0
      ? ((lastClose - firstClose) / firstClose) * 100
      : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-950 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-zinc-500 hover:text-zinc-100 text-xl leading-none"
          aria-label="Close"
        >
          ×
        </button>

        <div className="mb-4">
          <h2 className="text-2xl font-semibold text-zinc-100">
            {data?.base ?? symbol}
            {desc?.name && desc.name !== (data?.base ?? symbol) && (
              <span className="text-sm font-normal text-zinc-400 ml-2">
                {desc.name}
              </span>
            )}
          </h2>
          <p className="text-xs text-zinc-500 mt-1">
            {data
              ? `${data.asset_class.replace("_", " ")} · ${data.interval} bars · last 90 days`
              : "Loading…"}
          </p>
          {desc?.description && (
            <p className="text-xs text-zinc-400 mt-2 leading-relaxed max-w-3xl">
              {desc.description}
            </p>
          )}
        </div>

        {error && (
          <div className="rounded-md border border-rose-700/40 bg-rose-900/20 px-3 py-2 text-sm text-rose-200">
            {error}
          </div>
        )}

        {data && (
          <>
            <div className="flex items-baseline gap-3 mb-2">
              <span className="text-3xl font-medium text-zinc-100 tabular-nums">
                ${fmtPrice(lastClose ?? 0)}
              </span>
              {pctChange !== null && (
                <span
                  className={`text-sm tabular-nums ${
                    pctChange >= 0 ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {pctChange >= 0 ? "+" : ""}
                  {pctChange.toFixed(2)}% over window
                </span>
              )}
            </div>

            <PriceChart detail={data} />
            <ScoreChart detail={data} />

            <AskWhyPanel
              symbol={data.base}
              assetClass={data.asset_class}
              result={askResult}
              loading={askLoading}
              onAsk={async () => {
                setAskLoading(true);
                try {
                  const r = await fetchAskWhy(data.base, data.asset_class);
                  setAskResult(r);
                } catch (e) {
                  setAskResult({
                    status: "error",
                    message: e instanceof Error ? e.message : String(e),
                  });
                } finally {
                  setAskLoading(false);
                }
              }}
            />

            <EarningsSummaryPanel
              symbol={data.base}
              result={earningsResult}
              loading={earningsLoading}
              onAsk={async () => {
                setEarningsLoading(true);
                try {
                  const r = await fetchEarningsSummary(data.base);
                  setEarningsResult(r);
                } catch (e) {
                  setEarningsResult({
                    status: "error",
                    message: e instanceof Error ? e.message : String(e),
                  });
                } finally {
                  setEarningsLoading(false);
                }
              }}
            />

            {/* Position planning — Pro-gated, one-click open */}
            {isPro ? (
              <div className="mt-4">
                {showPlan ? (
                  <PlanningCard symbol={data.base} />
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowPlan(true)}
                    className="w-full rounded-md border border-blue-600/40 bg-blue-500/5 hover:bg-blue-500/10 px-4 py-3 text-sm text-blue-200 flex items-center justify-between transition"
                  >
                    <span className="text-left">
                      🎯 <strong>Show position plan for {data.base}</strong>
                      <span className="block text-[11px] text-blue-300/70 mt-0.5">
                        Extremum zone · entry ladder · ring-fence · historical context
                      </span>
                    </span>
                    <span className="text-lg">▸</span>
                  </button>
                )}
              </div>
            ) : (
              <div className="mt-4">
                <a
                  href="/pricing"
                  className="block rounded-md border border-indigo-500/40 bg-indigo-500/5 px-4 py-3 text-sm text-indigo-200 hover:bg-indigo-500/10 transition"
                >
                  🔒 <strong>Position planner</strong> — zone, entry ladder, ring-fence, historical context.
                  <span className="text-indigo-300/70"> Included with Pro →</span>
                </a>
              </div>
            )}

            <div className="mt-6">
              <h3 className="text-sm font-semibold text-zinc-300 mb-2">
                Recent headlines ({data.headlines.length})
              </h3>
              {data.headlines.length === 0 ? (
                <p className="text-xs text-zinc-500">
                  No headlines in the last 7 days for this symbol.
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {data.headlines.map((h, i) => (
                    <li
                      key={`${h.ts}-${i}`}
                      className="text-xs leading-tight border-b border-zinc-800/40 pb-1.5"
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <a
                          href={h.url ?? "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-zinc-200 hover:text-zinc-50 hover:underline flex-1"
                        >
                          {h.headline}
                        </a>
                        <span
                          className={`tabular-nums text-[11px] shrink-0 ${sentimentColor(
                            h.sentiment,
                          )}`}
                        >
                          {h.sentiment !== null
                            ? `${h.sentiment >= 0 ? "+" : ""}${h.sentiment.toFixed(2)}`
                            : "—"}
                        </span>
                      </div>
                      <div className="text-zinc-600 text-[10px] mt-0.5">
                        {h.publisher ?? "unknown"} ·{" "}
                        {new Date(h.ts + "Z").toLocaleString()}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-[10px] text-zinc-600 mt-6 leading-tight">
              {data.disclaimer}
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function PriceChart({ detail }: { detail: SymbolDetail }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 240,
      layout: {
        background: { type: ColorType.Solid, color: "#09090b" },
        textColor: "#a1a1aa",
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      rightPriceScale: { borderColor: "#27272a" },
      timeScale: { borderColor: "#27272a", timeVisible: true },
    });
    chartRef.current = chart;

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#60a5fa",
      topColor: "rgba(96, 165, 250, 0.35)",
      bottomColor: "rgba(96, 165, 250, 0.02)",
      priceFormat: {
        type: "price",
        precision: detail.price_series[0]?.close < 1 ? 4 : 2,
        minMove: detail.price_series[0]?.close < 1 ? 0.0001 : 0.01,
      },
    });

    series.setData(
      detail.price_series.map((p) => ({
        time: (new Date(p.ts + "Z").getTime() / 1000) as UTCTimestamp,
        value: p.close,
      })),
    );
    chart.timeScale().fitContent();

    const onResize = () => {
      if (ref.current && chartRef.current) {
        chartRef.current.applyOptions({ width: ref.current.clientWidth });
      }
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [detail]);

  return (
    <div>
      <div className="text-[11px] text-zinc-500 mb-1">Price</div>
      <div ref={ref} className="w-full" />
    </div>
  );
}

function AskWhyPanel({
  symbol,
  assetClass,
  result,
  loading,
  onAsk,
}: {
  symbol: string;
  assetClass: string;
  result: AskWhyResult | null;
  loading: boolean;
  onAsk: () => void;
}) {
  return (
    <div className="mt-6 rounded-md border border-zinc-800 bg-zinc-900/40 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">
            🤖 Ask why {symbol} is moving
          </h3>
          <p className="text-[11px] text-zinc-500 mt-0.5">
            Claude reads recent prices, headlines, and smart-money disclosures —
            then explains it in 4-6 plain-English sentences.
          </p>
        </div>
        <button
          onClick={onAsk}
          disabled={loading}
          className="shrink-0 rounded-md bg-amber-600/20 border border-amber-600/40 px-3 py-1.5 text-xs text-amber-200 hover:bg-amber-600/30 disabled:opacity-50 disabled:cursor-not-allowed transition"
          aria-label={`Ask AI why ${symbol} is moving (${assetClass})`}
        >
          {loading ? "Thinking…" : result?.status === "ok" ? "Re-explain" : "Ask"}
        </button>
      </div>

      {result?.status === "ok" && (
        <div className="mt-3 rounded bg-zinc-950/60 border border-zinc-800 p-3">
          <p className="text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap">
            {result.explanation}
          </p>
          <p className="text-[10px] text-zinc-600 mt-2">
            AI-generated · cross-check with the headlines and chart below.
          </p>
        </div>
      )}
      {result?.status === "pending" && (
        <div className="mt-3 rounded bg-amber-950/30 border border-amber-700/40 p-3">
          <p className="text-xs text-amber-200">{result.message}</p>
        </div>
      )}
      {result?.status === "free_tier" && (
        <div className="mt-3 rounded bg-indigo-950/30 border border-indigo-700/40 p-3">
          <p className="text-xs text-indigo-200">{result.message}</p>
          <a
            href="/pricing"
            className="inline-block mt-2 text-[11px] text-indigo-100 underline hover:text-white"
          >
            See plans →
          </a>
        </div>
      )}
      {result?.status === "thin_data" && (
        <div className="mt-3 rounded bg-zinc-950/60 border border-zinc-800 p-3">
          <p className="text-xs text-zinc-400">{result.message}</p>
        </div>
      )}
      {result?.status === "error" && (
        <div className="mt-3 rounded bg-rose-950/30 border border-rose-700/40 p-3">
          <p className="text-xs text-rose-200">{result.message}</p>
        </div>
      )}
    </div>
  );
}

function EarningsSummaryPanel({
  symbol,
  result,
  loading,
  onAsk,
}: {
  symbol: string;
  result: EarningsSummaryResult | null;
  loading: boolean;
  onAsk: () => void;
}) {
  return (
    <div className="mt-4 rounded-md border border-zinc-800 bg-zinc-900/40 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">
            📊 Earnings recap
          </h3>
          <p className="text-[11px] text-zinc-500 mt-0.5">
            Claude summarizes price reaction + headlines + signal change around
            {symbol}'s most recent earnings event.
          </p>
        </div>
        <button
          onClick={onAsk}
          disabled={loading}
          className="shrink-0 rounded-md bg-purple-600/20 border border-purple-600/40 px-3 py-1.5 text-xs text-purple-200 hover:bg-purple-600/30 disabled:opacity-50 disabled:cursor-not-allowed transition"
          aria-label={`Generate earnings summary for ${symbol}`}
        >
          {loading
            ? "Generating…"
            : result?.status === "ok"
              ? "Re-summarize"
              : "Summarize"}
        </button>
      </div>

      {result?.status === "ok" && (
        <div className="mt-3 rounded bg-zinc-950/60 border border-zinc-800 p-3">
          <p className="text-[11px] text-zinc-500 mb-2">
            Earnings event: <span className="text-zinc-300">{result.earnings_date}</span>
            {result.cached && (
              <span className="ml-2 px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[10px]">
                cached
              </span>
            )}
          </p>
          <p className="text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap">
            {result.summary}
          </p>
        </div>
      )}
      {result?.status === "pending" && (
        <div className="mt-3 rounded bg-amber-950/30 border border-amber-700/40 p-3">
          <p className="text-xs text-amber-200">{result.message}</p>
        </div>
      )}
      {result?.status === "free_tier" && (
        <div className="mt-3 rounded bg-indigo-950/30 border border-indigo-700/40 p-3">
          <p className="text-xs text-indigo-200">{result.message}</p>
          <a
            href="/pricing"
            className="inline-block mt-2 text-[11px] text-indigo-100 underline hover:text-white"
          >
            See plans →
          </a>
        </div>
      )}
      {result?.status === "no_data" && (
        <div className="mt-3 rounded bg-zinc-950/60 border border-zinc-800 p-3">
          <p className="text-xs text-zinc-400">{result.message}</p>
        </div>
      )}
      {result?.status === "error" && (
        <div className="mt-3 rounded bg-rose-950/30 border border-rose-700/40 p-3">
          <p className="text-xs text-rose-200">{result.message}</p>
        </div>
      )}
    </div>
  );
}

function ScoreChart({ detail }: { detail: SymbolDetail }) {
  const ref = useRef<HTMLDivElement>(null);
  const hasScores = detail.price_series.some((p) => p.score !== null);

  useEffect(() => {
    if (!hasScores || !ref.current) return;
    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 120,
      layout: {
        background: { type: ColorType.Solid, color: "#09090b" },
        textColor: "#a1a1aa",
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      rightPriceScale: { borderColor: "#27272a" },
      timeScale: { borderColor: "#27272a", timeVisible: true },
    });

    const series = chart.addSeries(LineSeries, {
      color: "#fbbf24",
      lineWidth: 2,
      priceFormat: { type: "price", precision: 3, minMove: 0.001 },
    });
    series.setData(
      detail.price_series
        .filter((p) => p.score !== null)
        .map((p) => ({
          time: (new Date(p.ts + "Z").getTime() / 1000) as UTCTimestamp,
          value: p.score!,
        })),
    );
    chart.timeScale().fitContent();

    const onResize = () => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, [detail, hasScores]);

  if (!hasScores) return null;

  return (
    <div className="mt-4">
      <div className="text-[11px] text-zinc-500 mb-1">
        Signal score (where computed)
      </div>
      <div ref={ref} className="w-full" />
    </div>
  );
}
