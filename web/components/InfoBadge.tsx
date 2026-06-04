/**
 * Small badge with an in-UI explanation popover. Used for NEG NEWS, INVERSE,
 * EARNINGS, etc. Click to toggle; closes on outside click or Esc.
 *
 * Tooltips that only show on hover are inaccessible on mobile and to keyboard
 * users — popovers triggered by click work everywhere.
 */

"use client";

import { useEffect, useRef, useState } from "react";

export function InfoBadge({
  label,
  tone = "amber",
  explanation,
  size = "sm",
}: {
  label: string;
  tone?: "amber" | "rose" | "emerald" | "zinc";
  explanation: string;
  size?: "sm" | "xs";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toneClasses = {
    amber: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    rose: "border-rose-500/40 bg-rose-500/10 text-rose-300",
    emerald: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
    zinc: "border-zinc-700 bg-zinc-800 text-zinc-300",
  }[tone];

  const sizeClasses =
    size === "xs"
      ? "text-[10px] px-1.5 py-0.5"
      : "text-[11px] px-2 py-0.5";

  return (
    <span ref={ref} className="relative inline-block">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className={`${sizeClasses} rounded border ${toneClasses} cursor-help hover:brightness-125 transition`}
        aria-expanded={open}
      >
        {label}
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute z-30 left-0 top-full mt-1 w-64 text-[11px] leading-snug p-2 rounded-md border border-zinc-700 bg-zinc-900 text-zinc-200 shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          {explanation}
        </span>
      )}
    </span>
  );
}
