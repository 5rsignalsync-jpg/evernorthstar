"use client";

import { useState } from "react";
import { useWatchlist } from "@/hooks/useWatchlist";

export function StarButton({
  symbol,
  asset_class,
  base,
  size = "sm",
}: {
  symbol: string;
  asset_class: string;
  base?: string;
  size?: "sm" | "md";
}) {
  const { isOn, toggle, max } = useWatchlist();
  const on = isOn(symbol, asset_class);
  const [shake, setShake] = useState(false);

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        const result = toggle({ symbol, asset_class, base });
        if (result === "limit_reached") {
          setShake(true);
          setTimeout(() => setShake(false), 400);
          alert(
            `Free tier limited to ${max} watchlist tickers. ` +
              `Upgrade to Pro for unlimited (see /pricing).`,
          );
        }
      }}
      className={
        (size === "md" ? "text-base" : "text-sm") +
        " leading-none px-1 transition-colors " +
        (on
          ? "text-amber-300 hover:text-amber-200"
          : "text-zinc-600 hover:text-zinc-300") +
        (shake ? " animate-pulse" : "")
      }
      aria-label={on ? `Remove ${base ?? symbol} from watchlist` : `Add ${base ?? symbol} to watchlist`}
      title={on ? "Remove from watchlist" : "Add to watchlist"}
    >
      {on ? "★" : "☆"}
    </button>
  );
}
