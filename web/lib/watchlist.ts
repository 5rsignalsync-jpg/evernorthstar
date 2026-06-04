/**
 * Watchlist persistence. Single localStorage key holds the set of starred
 * `(asset_class, symbol)` pairs so a watched symbol survives reloads + tab
 * switches. Keyed on (asset_class, symbol) because the same `AAPL`-style
 * shortname could exist in multiple universes later.
 */

const STORAGE_KEY = "crypto-trends:watchlist:v1";

export type WatchKey = {
  symbol: string;
  asset_class: string;
  base?: string;
};

function readRaw(): WatchKey[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (x): x is WatchKey =>
        x && typeof x.symbol === "string" && typeof x.asset_class === "string",
    );
  } catch {
    return [];
  }
}

function writeRaw(items: WatchKey[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    window.dispatchEvent(new CustomEvent("crypto-trends:watchlist-updated"));
  } catch {
    /* localStorage full / disabled — fail silent */
  }
}

/** Free-tier client-side cap. Server-side gating is enforced separately for
 * any future watchlist-sync API. */
export const FREE_WATCHLIST_MAX = 5;

export function getWatchlist(): WatchKey[] {
  return readRaw();
}

export function isWatched(symbol: string, asset_class: string): boolean {
  return readRaw().some(
    (w) => w.symbol === symbol && w.asset_class === asset_class,
  );
}

export type ToggleResult = "added" | "removed" | "limit_reached";

export function toggleWatched(
  item: WatchKey,
  maxAllowed: number = Infinity,
): ToggleResult {
  const list = readRaw();
  const idx = list.findIndex(
    (w) => w.symbol === item.symbol && w.asset_class === item.asset_class,
  );
  if (idx >= 0) {
    list.splice(idx, 1);
    writeRaw(list);
    return "removed";
  }
  if (list.length >= maxAllowed) {
    return "limit_reached";
  }
  list.push(item);
  writeRaw(list);
  return "added";
}

export function clearWatchlist(): void {
  writeRaw([]);
}
