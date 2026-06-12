"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createAlertRule,
  deleteAlertRule,
  listAlertEvents,
  listAlertRules,
  toggleAlertRule,
  type AlertCondition,
  type AlertEvent,
  type AlertRule,
} from "@/lib/api";

const CONDITION_LABELS: Record<AlertCondition, string> = {
  score_above: "Score above",
  score_below: "Score below",
  price_above: "Price above",
  price_below: "Price below",
};

const ASSET_CLASSES = ["equity_large", "equity_micro", "crypto", "crypto_micro"];

function fmtThreshold(rule: AlertRule): string {
  const isPrice = rule.condition.startsWith("price_");
  return isPrice
    ? `$${rule.threshold.toFixed(2)}`
    : `${rule.threshold >= 0 ? "+" : ""}${rule.threshold.toFixed(3)}`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "never";
  try {
    return new Date(iso + "Z").toLocaleString();
  } catch {
    return iso;
  }
}

export function AlertsSection({ isPro }: { isPro: boolean }) {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [symbol, setSymbol] = useState("");
  const [assetClass, setAssetClass] = useState("equity_large");
  const [condition, setCondition] = useState<AlertCondition>("score_above");
  const [threshold, setThreshold] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, e] = await Promise.all([listAlertRules(), listAlertEvents(10)]);
      setRules(r);
      setEvents(e);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const t = parseFloat(threshold);
    if (!symbol.trim() || Number.isNaN(t)) {
      setError("Symbol and threshold are required.");
      return;
    }
    setSubmitting(true);
    try {
      await createAlertRule({
        symbol: symbol.trim().toUpperCase(),
        asset_class: assetClass,
        condition,
        threshold: t,
        note: note.trim() || null,
      });
      setSymbol("");
      setThreshold("");
      setNote("");
      setShowForm(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(id: number) {
    setError(null);
    try {
      await deleteAlertRule(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function onToggle(rule: AlertRule) {
    setError(null);
    try {
      await toggleAlertRule(rule.id, !rule.enabled);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const activeCount = rules.filter((r) => r.enabled).length;
  const freeCapped = !isPro && activeCount >= 3;

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5 mb-4">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm uppercase tracking-wider text-zinc-500">
            Email alerts
          </h2>
          <p className="text-xs text-zinc-500 mt-1">
            Get an email when a ticker's score or price crosses your threshold.
            6-hour cooldown per rule.
            {!isPro && (
              <span className="text-amber-400/80">
                {" "}Free tier: 3 active rules ({activeCount}/3 used).
              </span>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          disabled={freeCapped && !showForm}
          className="shrink-0 rounded-md bg-blue-600/20 border border-blue-600/40 px-3 py-1.5 text-xs text-blue-200 hover:bg-blue-600/30 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {showForm ? "Cancel" : "+ New alert"}
        </button>
      </div>

      {error && (
        <p className="text-[11px] text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-2 py-1.5 mb-3">
          {error}
        </p>
      )}

      {showForm && (
        <form onSubmit={onSubmit} className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3 mb-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="text-[11px] text-zinc-400">Symbol</span>
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="AAPL"
                className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
                required
              />
            </label>
            <label className="block">
              <span className="text-[11px] text-zinc-400">Asset class</span>
              <select
                value={assetClass}
                onChange={(e) => setAssetClass(e.target.value)}
                className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100 focus:border-blue-500 focus:outline-none"
              >
                {ASSET_CLASSES.map((ac) => (
                  <option key={ac} value={ac}>{ac.replace("_", " ")}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-[11px] text-zinc-400">Condition</span>
              <select
                value={condition}
                onChange={(e) => setCondition(e.target.value as AlertCondition)}
                className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100 focus:border-blue-500 focus:outline-none"
              >
                {Object.entries(CONDITION_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-[11px] text-zinc-400">
                Threshold {condition.startsWith("score") ? "(score, -1 to +1)" : "(USD)"}
              </span>
              <input
                type="number"
                step={condition.startsWith("score") ? "0.01" : "0.01"}
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                placeholder={condition.startsWith("score") ? "0.5" : "150"}
                className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
                required
              />
            </label>
          </div>
          <label className="block">
            <span className="text-[11px] text-zinc-400">
              Note (optional, included in the email)
            </span>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={200}
              placeholder="e.g. 'cover my short here'"
              className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
            />
          </label>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition"
            >
              {submitting ? "Saving…" : "Save alert"}
            </button>
          </div>
        </form>
      )}

      {loading && rules.length === 0 ? (
        <p className="text-xs text-zinc-500">Loading…</p>
      ) : rules.length === 0 ? (
        <p className="text-xs text-zinc-500">
          No alerts yet. Click <em>+ New alert</em> to set one up.
        </p>
      ) : (
        <ul className="divide-y divide-zinc-800/60">
          {rules.map((r) => (
            <li key={r.id} className="py-2 flex items-center gap-3 text-sm">
              <button
                type="button"
                role="switch"
                aria-checked={r.enabled}
                onClick={() => onToggle(r)}
                className={
                  "shrink-0 inline-flex items-center h-5 w-9 rounded-full transition " +
                  (r.enabled ? "bg-emerald-500/70" : "bg-zinc-700")
                }
              >
                <span
                  className={
                    "h-4 w-4 rounded-full bg-white shadow transition-transform " +
                    (r.enabled ? "translate-x-4" : "translate-x-0.5")
                  }
                />
              </button>
              <div className="flex-1 min-w-0">
                <div className="text-zinc-100 font-medium tabular-nums">
                  {r.symbol}{" "}
                  <span className="text-zinc-400 font-normal text-xs">
                    {CONDITION_LABELS[r.condition]} {fmtThreshold(r)}
                  </span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-0.5">
                  {r.asset_class.replace("_", " ")} ·{" "}
                  Last triggered: {fmtDate(r.last_triggered_at)}
                  {r.note && <> · <em>{r.note}</em></>}
                </div>
              </div>
              <button
                type="button"
                onClick={() => onDelete(r.id)}
                className="shrink-0 text-[11px] text-zinc-500 hover:text-rose-400 transition"
                aria-label={`Delete alert ${r.symbol}`}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}

      {events.length > 0 && (
        <details className="mt-4 text-xs">
          <summary className="cursor-pointer text-zinc-400 hover:text-zinc-200 select-none">
            Recent trigger history ({events.length})
          </summary>
          <ul className="mt-2 space-y-1 text-[11px] text-zinc-500 max-h-40 overflow-y-auto pr-2">
            {events.map((e) => {
              const rule = rules.find((r) => r.id === e.rule_id);
              return (
                <li key={e.id} className="border-b border-zinc-800/40 pb-1">
                  <span className="text-zinc-300">
                    {rule?.symbol ?? `rule#${e.rule_id}`}
                  </span>{" "}
                  fired at {fmtDate(e.triggered_at)} · observed{" "}
                  <span className="tabular-nums">{e.observed_value.toFixed(3)}</span>
                  {e.email_sent ? " · ✉️ sent" : " · ⚠ email skipped"}
                </li>
              );
            })}
          </ul>
        </details>
      )}
    </div>
  );
}
