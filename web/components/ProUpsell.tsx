"use client";

import Link from "next/link";

/**
 * Compact upsell block shown inline below a Free-tier-limited table or
 * strategy. Honest, low-pressure — links to /pricing rather than nagging
 * inside a modal.
 */
export function ProUpsell({
  text,
  variant = "inline",
}: {
  text: string;
  variant?: "inline" | "card";
}) {
  if (variant === "card") {
    return (
      <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h3 className="text-sm font-semibold text-amber-200 mb-1">
              Want the full picture?
            </h3>
            <p className="text-xs text-amber-200/80 leading-relaxed max-w-md">
              {text}
            </p>
          </div>
          <Link
            href="/pricing"
            className="shrink-0 px-3 py-1.5 rounded-md bg-amber-500/20 border border-amber-500/40 text-amber-100 hover:bg-amber-500/30 text-xs font-medium"
          >
            See pricing →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-2 flex items-center justify-between text-[11px] text-zinc-500 border-t border-zinc-800/60 pt-2">
      <span>{text}</span>
      <Link
        href="/pricing"
        className="text-amber-300 hover:text-amber-200 underline decoration-dotted"
      >
        Upgrade
      </Link>
    </div>
  );
}
