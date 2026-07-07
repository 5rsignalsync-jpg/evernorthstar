"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type AdminUserSummary,
  type CompTier,
  compUser,
  listAdminUsers,
  uncompUser,
} from "@/lib/admin";

// Small admin panel on /account, visible only when the current session user
// has is_admin=True. Deliberately minimal — comp/uncomp + a compact users list.
// Anything more (search, bulk actions, tier stats) can move to its own page.
export function AdminPanel() {
  const [email, setEmail] = useState("");
  const [tier, setTier] = useState<CompTier>("pro");
  const [note, setNote] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [usersLoading, setUsersLoading] = useState(true);

  const refreshUsers = useCallback(async () => {
    setUsersError(null);
    try {
      const rows = await listAdminUsers(25);
      setUsers(rows);
    } catch (e) {
      setUsersError(e instanceof Error ? e.message : String(e));
    } finally {
      setUsersLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUsers();
  }, [refreshUsers]);

  const handleComp = async (action: "comp" | "uncomp") => {
    setError(null);
    setResult(null);
    if (!email.trim()) {
      setError("Enter an email");
      return;
    }
    setBusy(true);
    try {
      const res =
        action === "comp"
          ? await compUser(email.trim(), tier, note.trim() || undefined)
          : await uncompUser(email.trim());
      setResult(
        `${res.email} → ${res.tier} · ${res.action}${
          res.note ? ` · ${res.note}` : ""
        }`,
      );
      setEmail("");
      setNote("");
      await refreshUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-5 mb-4">
      <h2 className="text-sm uppercase tracking-wider text-amber-300 mb-1">
        Admin
      </h2>
      <p className="text-[11px] text-amber-200/60 mb-4">
        Comp/uncomp users. Only you see this section.
      </p>

      <div className="space-y-2 mb-4">
        <input
          type="email"
          placeholder="user@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full px-3 py-1.5 rounded-md bg-zinc-900 border border-zinc-700 text-zinc-100 text-sm placeholder:text-zinc-600 focus:border-amber-500/60 focus:outline-none"
        />
        <div className="flex gap-2">
          <select
            value={tier}
            onChange={(e) => setTier(e.target.value as CompTier)}
            className="px-2 py-1.5 rounded-md bg-zinc-900 border border-zinc-700 text-zinc-100 text-sm"
          >
            <option value="pro">Pro (lifetime)</option>
            <option value="founder_lifetime">Founder Lifetime</option>
          </select>
          <input
            type="text"
            placeholder="Note (optional, e.g. 'beta tester')"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="flex-1 px-3 py-1.5 rounded-md bg-zinc-900 border border-zinc-700 text-zinc-100 text-sm placeholder:text-zinc-600"
            maxLength={200}
          />
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleComp("comp")}
            disabled={busy}
            className="flex-1 py-1.5 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-100 hover:bg-emerald-500/30 text-sm font-medium disabled:opacity-50"
          >
            {busy ? "…" : "Comp → Pro"}
          </button>
          <button
            type="button"
            onClick={() => handleComp("uncomp")}
            disabled={busy}
            className="flex-1 py-1.5 rounded-md bg-rose-900/30 border border-rose-700/40 text-rose-200 hover:bg-rose-900/50 text-sm disabled:opacity-50"
          >
            Revoke → Free
          </button>
        </div>
      </div>

      {error && (
        <p className="text-[11px] text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-2 py-1.5 mb-2">
          {error}
        </p>
      )}
      {result && (
        <p className="text-[11px] text-emerald-200 border border-emerald-700/40 bg-emerald-900/20 rounded px-2 py-1.5 mb-2">
          {result}
        </p>
      )}

      <div className="mt-4">
        <div className="flex justify-between items-center mb-2">
          <p className="text-[11px] uppercase tracking-wider text-amber-300/80">
            Recent signups (last 25)
          </p>
          <button
            type="button"
            onClick={() => {
              setUsersLoading(true);
              void refreshUsers();
            }}
            className="text-[11px] text-amber-300/60 hover:text-amber-200"
          >
            ↻ Refresh
          </button>
        </div>
        {usersError && (
          <p className="text-[11px] text-rose-300">{usersError}</p>
        )}
        {usersLoading ? (
          <p className="text-[11px] text-zinc-500">Loading…</p>
        ) : (
          <div className="overflow-x-auto -mx-1">
            <table className="w-full text-[11px] tabular-nums">
              <thead>
                <tr className="text-amber-200/50 text-left border-b border-amber-500/20">
                  <th className="py-1 px-1 font-normal">Email</th>
                  <th className="py-1 px-1 font-normal">Tier</th>
                  <th className="py-1 px-1 font-normal">Signed up</th>
                  <th className="py-1 px-1 font-normal">Last login</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-amber-500/10">
                    <td className="py-1 px-1 text-zinc-200 truncate max-w-[180px]">
                      {u.email}
                      {u.is_admin && (
                        <span className="ml-1 text-amber-400">★</span>
                      )}
                    </td>
                    <td className="py-1 px-1">
                      <span
                        className={
                          u.subscription_tier === "free"
                            ? "text-zinc-500"
                            : u.subscription_tier === "founder_lifetime"
                              ? "text-amber-300"
                              : "text-emerald-300"
                        }
                      >
                        {u.subscription_tier}
                      </span>
                    </td>
                    <td className="py-1 px-1 text-zinc-500">
                      {formatShort(u.created_at)}
                    </td>
                    <td className="py-1 px-1 text-zinc-500">
                      {formatShort(u.last_login_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function formatShort(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}
