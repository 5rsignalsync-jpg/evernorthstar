"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { PasswordField } from "@/components/PasswordField";

export default function SignUpPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-up failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold tracking-tight mb-2">
          Join The<span className="text-emerald-400">Ever</span>Northstar
        </h1>
        <p className="text-sm text-zinc-500 mb-6">
          Free forever. Pro unlocks all sleeves, real-time refresh, and alerts.
        </p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs text-zinc-400 mb-1" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-400 mb-1" htmlFor="password">
              Password
            </label>
            <PasswordField
              id="password"
              autoComplete="new-password"
              value={password}
              onChange={setPassword}
            />
            <p className="text-[11px] text-zinc-500 mt-1">
              At least 8 characters. Use a password manager — this isn&apos;t a bank,
              but we hash with bcrypt and store nothing in plaintext.
            </p>
          </div>

          {error && (
            <p className="text-xs text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/30 text-sm font-medium disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create account"}
          </button>
        </form>

        <p className="text-[11px] text-zinc-600 mt-4 leading-relaxed">
          By creating an account you agree to our terms of service. We don&apos;t
          provide personalized investment advice — outputs are research signals
          only.
        </p>

        <p className="text-xs text-zinc-500 mt-6">
          Already have an account?{" "}
          <Link href="/sign-in" className="text-zinc-300 hover:text-zinc-100 underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
