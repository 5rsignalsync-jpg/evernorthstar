"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import {
  FREE_WATCHLIST_MAX,
  getWatchlist,
  isWatched,
  toggleWatched,
  type ToggleResult,
  type WatchKey,
} from "@/lib/watchlist";

const UPDATE_EVENT = "crypto-trends:watchlist-updated";

/** Subscribes to the persisted watchlist; re-renders on any change anywhere.
 * Respects free-tier 5-item limit; Pro users have no client-side cap. */
export function useWatchlist(): {
  items: WatchKey[];
  toggle: (item: WatchKey) => ToggleResult;
  isOn: (symbol: string, asset_class: string) => boolean;
  max: number;
  isAtLimit: boolean;
} {
  const { isPro } = useAuth();
  const max = isPro ? Infinity : FREE_WATCHLIST_MAX;
  const [items, setItems] = useState<WatchKey[]>([]);

  useEffect(() => {
    setItems(getWatchlist());
    const refresh = () => setItems(getWatchlist());
    window.addEventListener(UPDATE_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(UPDATE_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  const toggle = useCallback(
    (item: WatchKey): ToggleResult => toggleWatched(item, max),
    [max],
  );

  const isOn = useCallback(
    (symbol: string, asset_class: string) => isWatched(symbol, asset_class),
    // re-evaluate on items change
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [items],
  );

  return { items, toggle, isOn, max, isAtLimit: items.length >= max };
}
