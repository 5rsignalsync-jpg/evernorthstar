/**
 * Cheap, dependency-free shimmer skeletons. Used wherever we currently show
 * "Loading…" text so the UI doesn't go blank during a fetch.
 */

export function Skeleton({
  className = "",
  width,
  height,
}: {
  className?: string;
  width?: number | string;
  height?: number | string;
}) {
  return (
    <div
      className={
        "animate-pulse rounded bg-zinc-800/60 " + className
      }
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

/** Skeleton for a ranking-style table — 5 rows × full width. */
export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      <Skeleton className="h-5 w-1/3" />
      <div className="space-y-2">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-4 w-4" />
            <Skeleton className="h-4 flex-1 max-w-[120px]" />
            <Skeleton className="h-4 w-16 ml-auto" />
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Skeleton card for the strategy grid. */
export function CardSkeleton() {
  return (
    <div
      className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 space-y-2"
      aria-busy="true"
    >
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-3 w-10" />
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-4/5" />
      <Skeleton className="h-3 w-1/2 mt-2" />
    </div>
  );
}
