"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import {
  createCryptoPosition,
  deleteCryptoPosition,
  listCryptoPositions,
  updateCryptoPosition,
  type CryptoPosition,
  type CryptoPositionInput,
} from "@/lib/api";
import { PlanningCard } from "@/components/PlanningCard";

/**
 * Manual crypto positions section on /portfolio.
 * User types symbol + quantity + cost basis + optional exchange label; we
 * pull current price server-side from ohlcv. Aggregate value + allocation
 * bars up top. Click any row → PlanningCard expands with the full Merlin
 * engine (zones, entry ladder, ring-fence, historical outcomes).
 */

function fmtUSD(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !isFinite(v)) return "—";
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: digits,
  });
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined || !isFinite(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function fmtQty(v: number): string {
  if (v >= 1) return v.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return v.toLocaleString("en-US", { maximumFractionDigits: 8 });
}

export function CryptoPositionsSection() {
  const [positions, setPositions] = useState<CryptoPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Add / edit form state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [costBasis, setCostBasis] = useState("");
  const [exchange, setExchange] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPositions(await listCryptoPositions());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function resetForm() {
    setEditingId(null);
    setSymbol("");
    setQuantity("");
    setCostBasis("");
    setExchange("");
    setNotes("");
  }

  function startEdit(p: CryptoPosition) {
    setEditingId(p.id);
    setSymbol(p.symbol);
    setQuantity(String(p.quantity));
    setCostBasis(String(p.cost_basis_per_share));
    setExchange(p.exchange_label ?? "");
    setNotes(p.notes ?? "");
    setShowForm(true);
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const qty = parseFloat(quantity);
    const cost = parseFloat(costBasis);
    if (!symbol.trim() || Number.isNaN(qty) || qty <= 0 || Number.isNaN(cost) || cost <= 0) {
      setError("Symbol, positive quantity, and positive cost basis are required.");
      return;
    }
    const input: CryptoPositionInput = {
      symbol: symbol.trim().toUpperCase(),
      quantity: qty,
      cost_basis_per_share: cost,
      exchange_label: exchange.trim() || null,
      notes: notes.trim() || null,
    };
    setSubmitting(true);
    try {
      if (editingId) {
        await updateCryptoPosition(editingId, input);
      } else {
        await createCryptoPosition(input);
      }
      resetForm();
      setShowForm(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(p: CryptoPosition) {
    if (!confirm(`Delete your ${p.symbol} position? This can't be undone.`)) return;
    try {
      await deleteCryptoPosition(p.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  // Aggregation
  const totalCost = positions.reduce((s, p) => s + p.total_cost_usd, 0);
  const totalValue = positions.reduce(
    (s, p) => s + (p.current_value_usd ?? 0),
    0,
  );
  const unrealized = totalValue - totalCost;
  const unrealizedPct = totalCost > 0 ? (unrealized / totalCost) * 100 : null;

  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/40 p-4 mb-6">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100 uppercase tracking-wider">
            🪙 Manual crypto positions
          </h2>
          <p className="text-[11px] text-zinc-500 mt-0.5">
            Type your crypto holdings in directly. Every ranked ticker gets full
            planning support (zones, entry ladder, ring-fence).
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            if (showForm) {
              resetForm();
              setShowForm(false);
            } else {
              setShowForm(true);
            }
          }}
          className="shrink-0 rounded-md bg-blue-600/20 border border-blue-600/40 px-3 py-1.5 text-xs text-blue-200 hover:bg-blue-600/30 transition"
        >
          {showForm ? "Cancel" : "+ Add position"}
        </button>
      </div>

      {error && (
        <p className="text-[11px] text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-2 py-1.5 mb-3">
          {error}
        </p>
      )}

      {showForm && (
        <form
          onSubmit={onSubmit}
          className="rounded border border-zinc-800 bg-zinc-950/60 p-3 mb-3 grid grid-cols-1 sm:grid-cols-5 gap-2 items-end"
        >
          <label className="block">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">Symbol</span>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="BTC"
              className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
              required
            />
          </label>
          <label className="block">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">Quantity</span>
            <input
              type="number"
              step="any"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="0.5"
              className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
              required
            />
          </label>
          <label className="block">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">Cost / unit</span>
            <input
              type="number"
              step="any"
              value={costBasis}
              onChange={(e) => setCostBasis(e.target.value)}
              placeholder="32000"
              className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
              required
            />
          </label>
          <label className="block">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">Exchange (opt)</span>
            <input
              type="text"
              value={exchange}
              onChange={(e) => setExchange(e.target.value)}
              placeholder="Coinbase"
              className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50 h-fit"
          >
            {submitting ? "Saving…" : editingId ? "Update" : "Add"}
          </button>
          <label className="block sm:col-span-5">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">
              Notes (optional)
            </span>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={500}
              placeholder="Bought in the March dip"
              className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
            />
          </label>
        </form>
      )}

      {/* Aggregation cards */}
      {positions.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          <MetricCard label="Total cost" value={fmtUSD(totalCost, 0)} />
          <MetricCard label="Current value" value={fmtUSD(totalValue, 0)} />
          <MetricCard
            label="Unrealized"
            value={fmtUSD(unrealized, 0)}
            sub={unrealizedPct !== null ? fmtPct(unrealizedPct) : undefined}
            color={unrealized >= 0 ? "text-emerald-300" : "text-rose-300"}
          />
          <MetricCard label="Positions" value={String(positions.length)} />
        </div>
      )}

      {/* Allocation bars */}
      {positions.length > 1 && totalValue > 0 && (
        <div className="mb-4">
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">
            Allocation
          </p>
          <div className="space-y-1">
            {positions.map((p) => {
              const pct = ((p.current_value_usd ?? 0) / totalValue) * 100;
              return (
                <div key={`alloc-${p.id}`} className="flex items-center gap-3 text-[11px]">
                  <span className="w-14 text-zinc-300 font-medium tabular-nums">
                    {p.symbol}
                  </span>
                  <div className="flex-1 h-2.5 rounded bg-zinc-800/60 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                  <span className="w-14 text-right tabular-nums text-zinc-400">
                    {pct.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Position table */}
      {loading && positions.length === 0 ? (
        <p className="text-xs text-zinc-500">Loading…</p>
      ) : positions.length === 0 ? (
        <div className="rounded border border-dashed border-zinc-800 py-6 text-center text-xs text-zinc-500">
          No crypto positions yet. Click{" "}
          <em className="text-zinc-300">+ Add position</em> to start tracking BTC,
          ETH, SOL, or anything else in our universe.
        </div>
      ) : (
        <div className="rounded border border-zinc-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-[10px] text-zinc-500 uppercase tracking-wider bg-zinc-900/80">
              <tr>
                <th className="text-left px-3 py-2 w-6"></th>
                <th className="text-left px-3 py-2">Symbol</th>
                <th className="text-right px-3 py-2">Qty</th>
                <th className="text-right px-3 py-2">Cost / unit</th>
                <th className="text-right px-3 py-2">Now</th>
                <th className="text-right px-3 py-2">Value</th>
                <th className="text-right px-3 py-2">Gain</th>
                <th className="text-right px-3 py-2 w-24"></th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const isExpanded = expandedId === p.id;
                return (
                  <Fragment key={`row-${p.id}`}>
                    <tr
                      onClick={() =>
                        setExpandedId(isExpanded ? null : p.id)
                      }
                      className="border-t border-zinc-800/60 cursor-pointer hover:bg-zinc-800/30"
                    >
                      <td className="px-3 py-2 text-zinc-500 text-xs">
                        {isExpanded ? "▾" : "▸"}
                      </td>
                      <td className="px-3 py-2 font-medium text-zinc-100 tabular-nums">
                        {p.symbol}
                        {p.exchange_label && (
                          <span className="text-[10px] text-zinc-500 ml-2">
                            {p.exchange_label}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-zinc-300">
                        {fmtQty(p.quantity)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-zinc-300">
                        {fmtUSD(p.cost_basis_per_share)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-zinc-200">
                        {fmtUSD(p.current_price)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-zinc-200">
                        {fmtUSD(p.current_value_usd, 0)}
                      </td>
                      <td
                        className={
                          "px-3 py-2 text-right tabular-nums " +
                          ((p.unrealized_gain_usd ?? 0) >= 0
                            ? "text-emerald-300"
                            : "text-rose-300")
                        }
                      >
                        {fmtUSD(p.unrealized_gain_usd, 0)}
                        <div className="text-[10px] text-zinc-500">
                          {fmtPct(p.unrealized_gain_pct)}
                        </div>
                      </td>
                      <td
                        className="px-3 py-2 text-right text-[11px]"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          type="button"
                          onClick={() => startEdit(p)}
                          className="text-zinc-400 hover:text-zinc-100 mr-2"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void onDelete(p)}
                          className="text-zinc-500 hover:text-rose-400"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={8} className="px-3 py-3 bg-zinc-950/40">
                          <PlanningCard
                            symbol={p.symbol}
                            quantity={p.quantity}
                            costBasisPerShare={p.cost_basis_per_share}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MetricCard({
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
    <div className="rounded border border-zinc-800 bg-zinc-900/40 px-3 py-2">
      <p className="text-[10px] text-zinc-500 uppercase tracking-wider">
        {label}
      </p>
      <p className={`text-base font-semibold tabular-nums mt-0.5 ${color ?? "text-zinc-100"}`}>
        {value}
      </p>
      {sub && <p className={`text-[10px] tabular-nums ${color ?? "text-zinc-500"}`}>{sub}</p>}
    </div>
  );
}
