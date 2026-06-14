"use client";

import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import {
  createPlaidLinkToken,
  exchangePlaidPublicToken,
  type BrokerageAccount,
} from "@/lib/api";

/**
 * Opens Plaid Link → exchanges the resulting public_token for a backend
 * BrokerageAccount → invokes `onLinked` so the parent can refetch portfolio.
 *
 * Plaid Link fetches its own JS from cdn.plaid.com when usePlaidLink mounts.
 * We get the short-lived link_token from our backend (which holds the Plaid
 * secret). The user never sees brokerage credentials.
 */
export function PlaidLinkButton({
  onLinked,
  className,
  label = "+ Connect brokerage",
}: {
  onLinked: (account: BrokerageAccount) => void;
  className?: string;
  label?: string;
}) {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const requestLinkToken = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const { link_token } = await createPlaidLinkToken();
      setLinkToken(link_token);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const onSuccess = useCallback(
    async (publicToken: string) => {
      setLoading(true);
      try {
        const account = await exchangePlaidPublicToken(publicToken);
        onLinked(account);
        setLinkToken(null);   // force a fresh token next time
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [onLinked],
  );

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess: (publicToken) => {
      void onSuccess(publicToken);
    },
    onExit: () => {
      // user closed the modal — no action needed; they can click button again
    },
  });

  // Auto-open Plaid Link as soon as we have a token + Plaid SDK is ready.
  useEffect(() => {
    if (linkToken && ready) {
      open();
    }
  }, [linkToken, ready, open]);

  return (
    <div className="inline-block">
      <button
        type="button"
        onClick={() => void requestLinkToken()}
        disabled={loading}
        className={
          className ??
          "rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition"
        }
      >
        {loading ? "Opening…" : label}
      </button>
      {error && (
        <p className="text-[11px] text-rose-300 border border-rose-700/40 bg-rose-900/20 rounded px-2 py-1.5 mt-2">
          {error.includes("503") || error.toLowerCase().includes("coming soon")
            ? "Brokerage sync is coming soon — Plaid integration is wired up but the deployment hasn't been provisioned with Plaid credentials yet."
            : error}
        </p>
      )}
    </div>
  );
}
