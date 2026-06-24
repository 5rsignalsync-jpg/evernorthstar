import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Shared shell for /legal/* pages. Centers content, sets a max-width for
 * legible long-form reading, and renders the same Back-to-dashboard chrome
 * everywhere so users never feel trapped in fine print.
 */
export function LegalPage({
  title,
  effectiveDate,
  children,
}: {
  title: string;
  effectiveDate: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6 md:p-10">
      <div className="max-w-3xl mx-auto">
        <Link
          href="/"
          className="text-xs text-zinc-500 hover:text-zinc-300 mb-6 inline-block"
        >
          ← Back to dashboard
        </Link>
        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight mb-1">
          {title}
        </h1>
        <p className="text-xs text-zinc-500 mb-8">
          Effective date: {effectiveDate} · EverNorthstar is a product of
          5Royals Investments LLC.
        </p>

        <article className="prose prose-invert prose-zinc max-w-none text-sm leading-relaxed [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-8 [&_h2]:mb-2 [&_h2]:text-zinc-100 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-4 [&_h3]:mb-1 [&_h3]:text-zinc-200 [&_p]:text-zinc-300 [&_p]:mb-3 [&_ul]:my-3 [&_ul]:pl-5 [&_ul]:list-disc [&_li]:text-zinc-300 [&_li]:mb-1 [&_a]:text-blue-400 [&_a:hover]:text-blue-300 [&_strong]:text-zinc-100">
          {children}
        </article>

        <p className="text-[11px] text-zinc-600 mt-12 border-t border-zinc-800 pt-4 leading-relaxed">
          This document is provided for transparency. It is not legal advice.
          Consult a qualified attorney before relying on it for your own
          situation.
        </p>
      </div>
    </main>
  );
}
