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
  fetchSymbolDetail,
  fetchTickerDescription,
  type SymbolDetail,
  type TickerDescription,
} from "@/lib/api";

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
  const [data, setData] = useState<SymbolDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [desc, setDesc] = useState<TickerDescription | null>(null);

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
