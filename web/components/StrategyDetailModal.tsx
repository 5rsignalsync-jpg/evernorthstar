"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchStrategyDetail,
  type StrategyDetail,
} from "@/lib/api";

function formatDollars(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function sideColor(side: string): string {
  if (side === "buy") return "text-emerald-300";
  if (side === "sell") return "text-rose-300";
  return "text-zinc-400";
}

export function StrategyDetailModal({
  slug,
  onClose,
  onSelectSymbol,
}: {
  slug: string;
  onClose: () => void;
  onSelectSymbol: (symbol: string) => void;
}) {
  const [portfolioSize, setPortfolioSize] = useState(10_000);
  const [data, setData] = useState<StrategyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    fetchStrategyDetail(slug, portfolioSize)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message ?? String(e)));
    return () => {
      cancelled = true;
    };
  }, [slug, portfolioSize]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

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

        {error && (
          <div className="rounded-md border border-rose-700/40 bg-rose-900/20 px-3 py-2 text-sm text-rose-200">
            {error}
          </div>
        )}

        {!data && !error && <p className="text-zinc-500 text-sm">Loading…</p>}

        {data && (
          <>
            <div className="mb-4">
              <h2 className="text-2xl font-semibold text-zinc-100">
                {data.card.emoji} {data.card.name}
                {data.inverse && (
                  <span className="ml-2 text-xs text-amber-300 font-normal align-middle">
                    INVERSE
                  </span>
                )}
              </h2>
              <p className="text-sm text-zinc-400 mt-2">{data.card.description}</p>
              {data.positions.length < data.card.n_positions && (
                <p className="text-xs text-amber-300 mt-2">
                  Showing {data.positions.length} of{" "}
                  {data.card.n_positions} positions ·{" "}
                  <Link
                    href="/pricing"
                    className="underline decoration-dotted hover:text-amber-200"
                    onClick={onClose}
                  >
                    Upgrade for the full basket
                  </Link>
                </p>
              )}
            </div>

            <div className="mb-5 flex items-center gap-3 text-sm">
              <label className="text-zinc-400">If you had</label>
              <select
                value={portfolioSize}
                onChange={(e) => setPortfolioSize(Number(e.target.value))}
                className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100"
              >
                {[1_000, 5_000, 10_000, 25_000, 100_000, 500_000].map((v) => (
                  <option key={v} value={v}>
                    {formatDollars(v)}
                  </option>
                ))}
              </select>
              <span className="text-zinc-400">
                to mirror this, the basket would suggest:
              </span>
            </div>

            <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 mb-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-zinc-500 text-xs uppercase tracking-wider">
                    <th className="text-left font-normal py-2">#</th>
                    <th className="text-left font-normal py-2">Ticker</th>
                    <th className="text-right font-normal py-2">Weight</th>
                    <th className="text-right font-normal py-2">Suggested $</th>
                    <th className="text-right font-normal py-2">Actor value</th>
                  </tr>
                </thead>
                <tbody>
                  {data.positions.map((p, i) => (
                    <tr
                      key={p.ticker}
                      className="border-t border-zinc-800/60 cursor-pointer hover:bg-zinc-800/30"
                      onClick={() => {
                        // Close *this* modal before the symbol modal opens —
                        // we don't want modal-on-modal stacking.
                        onClose();
                        onSelectSymbol(p.ticker);
                      }}
                    >
                      <td className="py-2 text-zinc-500">{i + 1}</td>
                      <td className="py-2 text-zinc-100 font-medium">{p.ticker}</td>
                      <td
                        className={`py-2 text-right tabular-nums ${
                          p.weight >= 0 ? "text-emerald-300" : "text-rose-300"
                        }`}
                      >
                        {(p.weight * 100).toFixed(2)}%
                      </td>
                      <td
                        className={`py-2 text-right tabular-nums ${
                          p.suggested_usd >= 0 ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {data.inverse ? "−" : ""}
                        {formatDollars(Math.abs(p.suggested_usd))}
                      </td>
                      <td className="py-2 text-right text-zinc-500 text-xs">
                        {formatDollars(p.value_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.positions.length === 0 && (
                <p className="text-xs text-zinc-500 py-3 text-center">
                  No positions to display.
                </p>
              )}
            </div>

            <div className="mb-5">
              <h3 className="text-sm font-semibold text-zinc-300 mb-2">
                Recent activity ({data.recent_activity.length})
              </h3>
              <ul className="space-y-1">
                {data.recent_activity.slice(0, 12).map((a, i) => (
                  <li
                    key={`${a.ticker}-${i}`}
                    className="text-xs leading-tight border-b border-zinc-800/40 pb-1 flex justify-between gap-3"
                  >
                    <span className="text-zinc-400">
                      <span className="text-zinc-500">{a.disclosure_date}</span>{" "}
                      <span className="text-zinc-200">{a.actor_name}</span>{" "}
                      <span className={sideColor(a.side)}>{a.side}</span>{" "}
                      <span className="text-zinc-200 font-medium">{a.ticker}</span>
                      {a.note && (
                        <span className="text-zinc-600 ml-1">· {a.note}</span>
                      )}
                    </span>
                    <span className="text-zinc-500 tabular-nums shrink-0">
                      {a.amount_usd ? formatDollars(a.amount_usd) : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {data.card.caveats.length > 0 && (
              <div className="rounded-md border border-amber-700/30 bg-amber-900/10 px-3 py-2 text-[11px] text-amber-200/90">
                <strong className="text-amber-200">Caveats:</strong>
                <ul className="list-disc ml-4 mt-1 space-y-0.5">
                  {data.card.caveats.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-[10px] text-zinc-600 mt-4 leading-tight">
              {data.disclaimer}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
