"use client";

import Link from "next/link";
import { useAuth } from "./AuthProvider";

export function AuthMenu() {
  const { user, loading, logout, isPro } = useAuth();

  if (loading) {
    return <div className="text-xs text-zinc-600">…</div>;
  }

  if (!user) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <Link
          href="/sign-in"
          className="text-zinc-300 hover:text-zinc-100"
        >
          Sign in
        </Link>
        <Link
          href="/sign-up"
          className="px-3 py-1 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/30 font-medium"
        >
          Sign up
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 text-sm">
      {isPro ? (
        <span className="text-[10px] px-1.5 py-0.5 rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 uppercase tracking-wider">
          Pro
        </span>
      ) : (
        <Link
          href="/pricing"
          className="text-[10px] px-1.5 py-0.5 rounded border border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 uppercase tracking-wider"
        >
          Upgrade
        </Link>
      )}
      <Link
        href="/account"
        className="text-zinc-400 text-xs hidden md:inline truncate max-w-[180px] hover:text-zinc-200 underline decoration-dotted underline-offset-2"
        title={`${user.email} — click for account settings`}
      >
        {user.email}
      </Link>
      <button
        onClick={() => logout()}
        className="text-zinc-500 hover:text-zinc-300 text-xs underline decoration-dotted"
      >
        Sign out
      </button>
    </div>
  );
}
