"use client";

import { useCallback, useEffect, useState } from "react";
import {
  connectExchange,
  deleteExchangeConnection,
  listExchangeConnections,
  listSupportedExchanges,
  syncExchangeConnection,
  type ExchangeConnection,
  type SupportedExchange,
} from "@/lib/api";

/**
 * Exchange auto-connect via CCXT.
 *
 * User pastes a READ-ONLY API key (+ secret, + optional passphrase) for
 * a whitelisted exchange. We test the credentials by fetching balances,
 * encrypt and store on success, and populate CryptoPositions tagged with
 * source='ccxt'. Balances refresh via a Sync button (no cron for MVP).
 *
 * Security: keys never leave the server after the initial POST. The
 * connection card shows an obvious "revoke on the exchange" reminder.
 */

function formatTime(iso: string | null): string {
  if (!iso) return "never";
  try {
    const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
    const diffMs = Date.now() - d.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function ExchangeConnectSection({
  onConnectionsChanged,
}: {
  onConnectionsChanged?: () => void;
}) {
  const [supported, setSupported] = useState<SupportedExchange[]>([]);
  const [connections, setConnections] = useState<ExchangeConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [exchangeId, setExchangeId] = useState("");
  const [displayLabel, setDisplayLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const chosen = supported.find((s) => s.id === exchangeId);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sup, cx] = await Promise.all([
        listSupportedExchanges(),
        listExchangeConnections(),
      ]);
      setSupported(sup);
      setConnections(cx);
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
    setExchangeId("");
    setDisplayLabel("");
    setApiKey("");
    setApiSecret("");
    setPassphrase("");
    setNotice(null);
  }

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (!chosen) {
      setError("Pick an exchange first.");
      return;
    }
    if (chosen.requires_passphrase && !passphrase.trim()) {
      setError(`${chosen.label} requires a passphrase.`);
      return;
    }
    setBusy(true);
    try {
      const r = await connectExchange({
        exchange_id: exchangeId,
        display_label: displayLabel.trim() || chosen.label,
        api_key: apiKey.trim(),
        api_secret: apiSecret.trim(),
        passphrase: chosen.requires_passphrase
          ? passphrase.trim()
          : undefined,
      });
      setNotice(
        `Connected ${r.connection.exchange_label} — imported ${r.positions_written} position${r.positions_written === 1 ? "" : "s"}.`,
      );
      resetForm();
      setShowForm(false);
      await refresh();
      onConnectionsChanged?.();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  }

  async function handleSync(c: ExchangeConnection) {
    setError(null);
    setNotice(null);
    try {
      const r = await syncExchangeConnection(c.id);
      setNotice(
        `Synced ${r.connection.exchange_label} — ${r.positions_written} position${r.positions_written === 1 ? "" : "s"}.`,
      );
      await refresh();
      onConnectionsChanged?.();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : String(e2));
    }
  }

  async function handleDelete(c: ExchangeConnection) {
    if (
      !confirm(
        `Disconnect ${c.exchange_label} (${c.display_label})? Positions from this connection will be removed. Manual entries with the same symbol stay.`,
      )
    )
      return;
    setError(null);
    try {
      await deleteExchangeConnection(c.id);
      await refresh();
      onConnectionsChanged?.();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : String(e2));
    }
  }

  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/40 p-4 mb-6">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100 uppercase tracking-wider">
            🔗 Exchange auto-connect
          </h2>
          <p className="text-[11px] text-zinc-500 mt-0.5">
            Read-only sync from {supported.length}+ exchanges via CCXT.
            EverNorthstar never trades, transfers, or withdraws.
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
          className="shrink-0 rounded-md bg-emerald-500/20 border border-emerald-500/40 px-3 py-1.5 text-xs text-emerald-100 hover:bg-emerald-500/30"
        >
          {showForm ? "Cancel" : "+ Connect exchange"}
        </button>
      </div>

      {error && (
        <p className="text-[11px] text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-2 py-1.5 mb-3">
          {error}
        </p>
      )}
      {notice && (
        <p className="text-[11px] text-emerald-200 border border-emerald-700/40 bg-emerald-900/20 rounded px-2 py-1.5 mb-3">
          {notice}
        </p>
      )}

      {showForm && (
        <form
          onSubmit={handleConnect}
          className="rounded border border-emerald-500/30 bg-zinc-950/60 p-3 mb-3 space-y-3"
        >
          <div className="rounded border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-200/90 leading-relaxed">
            ⚠️ <strong className="text-amber-200">Read-only keys only.</strong>{" "}
            Create a new API key on the exchange with view/read permission —
            <em> never</em> enable trading, withdrawal, or transfer. You can
            revoke this key any time from the exchange.
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <label className="block">
              <span className="text-[10px] text-zinc-400 uppercase tracking-wider">
                Exchange
              </span>
              <select
                value={exchangeId}
                onChange={(e) => {
                  setExchangeId(e.target.value);
                  const s = supported.find((x) => x.id === e.target.value);
                  if (s && !displayLabel) setDisplayLabel(s.label);
                }}
                className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-100"
                required
              >
                <option value="">Pick one…</option>
                {supported.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-[10px] text-zinc-400 uppercase tracking-wider">
                Nickname (any label)
              </span>
              <input
                type="text"
                value={displayLabel}
                onChange={(e) => setDisplayLabel(e.target.value)}
                placeholder={chosen?.label || "e.g. Coinbase Main"}
                maxLength={64}
                className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-100 placeholder:text-zinc-600"
              />
            </label>
          </div>

          {chosen && (
            <p className="text-[11px] text-zinc-400 leading-relaxed border-l-2 border-emerald-500/40 pl-2">
              {chosen.note}
            </p>
          )}

          <label className="block">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">
              API key
            </span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              autoComplete="off"
              className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm font-mono text-zinc-100"
              required
            />
          </label>
          <label className="block">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">
              API secret
            </span>
            <input
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              autoComplete="off"
              className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm font-mono text-zinc-100"
              required
            />
          </label>
          {chosen?.requires_passphrase && (
            <label className="block">
              <span className="text-[10px] text-zinc-400 uppercase tracking-wider">
                Passphrase ({chosen.label} requires it)
              </span>
              <input
                type="password"
                value={passphrase}
                onChange={(e) => setPassphrase(e.target.value)}
                autoComplete="off"
                className="block w-full mt-0.5 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm font-mono text-zinc-100"
                required
              />
            </label>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                resetForm();
                setShowForm(false);
              }}
              className="flex-1 py-1.5 rounded-md bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs hover:bg-zinc-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || !exchangeId}
              className="flex-1 py-1.5 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-xs font-medium disabled:opacity-50"
            >
              {busy ? "Testing…" : "Test + connect"}
            </button>
          </div>
        </form>
      )}

      {loading && connections.length === 0 ? (
        <p className="text-xs text-zinc-500">Loading…</p>
      ) : connections.length === 0 ? (
        <div className="rounded border border-dashed border-zinc-800 py-4 text-center text-[11px] text-zinc-500">
          No connected exchanges yet. Click{" "}
          <em className="text-zinc-300">+ Connect exchange</em> to import
          balances from Coinbase, Binance.US, Kraken, Gemini, KuCoin, Bybit,
          or OKX.
        </div>
      ) : (
        <div className="space-y-2">
          {connections.map((c) => (
            <div
              key={c.id}
              className={
                "rounded border p-3 flex items-center justify-between gap-3 " +
                (c.status === "error"
                  ? "border-rose-500/40 bg-rose-900/10"
                  : "border-zinc-800 bg-zinc-950/60")
              }
            >
              <div className="min-w-0">
                <p className="text-sm text-zinc-100 font-medium truncate">
                  {c.exchange_label}
                  <span className="text-zinc-500 ml-2 text-[11px]">
                    · {c.display_label}
                  </span>
                </p>
                <p className="text-[11px] text-zinc-500">
                  {c.positions_last_synced} position
                  {c.positions_last_synced === 1 ? "" : "s"} · synced{" "}
                  {formatTime(c.last_synced_at)}
                </p>
                {c.last_error && (
                  <p className="text-[10px] text-rose-300 mt-1 truncate">
                    {c.last_error}
                  </p>
                )}
              </div>
              <div className="flex gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={() => void handleSync(c)}
                  className="text-[11px] text-emerald-300 hover:text-emerald-200 px-2 py-1 rounded border border-emerald-500/30 hover:bg-emerald-500/10"
                >
                  ↻ Sync
                </button>
                <button
                  type="button"
                  onClick={() => void handleDelete(c)}
                  className="text-[11px] text-zinc-500 hover:text-rose-400 px-2 py-1 rounded border border-zinc-800 hover:border-rose-500/30"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
