import type { RankingRow } from "@/lib/api";
import { InfoBadge } from "./InfoBadge";
import { ProUpsell } from "./ProUpsell";
import { ScoreLegend } from "./ScoreLegend";
import { StarButton } from "./StarButton";

function scoreColor(score: number): string {
  if (score > 0.5) return "text-emerald-400";
  if (score > 0.2) return "text-emerald-300";
  if (score < -0.5) return "text-rose-400";
  if (score < -0.2) return "text-rose-300";
  return "text-zinc-400";
}

function pctColor(pct: number | null): string {
  if (pct === null) return "text-zinc-500";
  if (pct > 0) return "text-emerald-400";
  if (pct < 0) return "text-rose-400";
  return "text-zinc-400";
}

function directionArrow(value: number | null): string {
  if (value === null || value === 0) return "·";
  return value > 0 ? "▲" : "▼";
}

function formatPrice(p: number | null): string {
  if (p === null) return "—";
  if (p < 0.01) return p.toFixed(6);
  if (p < 1) return p.toFixed(4);
  if (p < 100) return p.toFixed(2);
  return p.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatComponent(value: number | null | undefined, kind: string): string {
  if (value === null || value === undefined) return "—";
  if (kind === "return_pct") return `${(value * 100).toFixed(1)}%`;
  if (kind === "rsi") return value.toFixed(0);
  return value.toFixed(2);
}

function componentLabel(key: string): string {
  return (
    {
      return_pct: "ret",
      rsi: "rsi",
      quality: "Q",
      value: "V",
      momentum: "M",
    } as Record<string, string>
  )[key] ?? key;
}

const NEG_NEWS_EXPLANATION =
  "Recent headlines for this ticker contain a high-confidence negative keyword "
  + "(bankruptcy, lawsuit, investigation, halt, etc.). This is a keyword filter — "
  + "not a sentiment score — and is much higher-confidence than the raw FinBERT "
  + "number. Avoid going long names with this flag unless you understand the story.";

const EARNINGS_EXPLANATION =
  "This ticker reports earnings within the next ~30 days. Going long into a "
  + "guidance cut is one of the most common ways momentum signals lose money — "
  + "size positions accordingly or wait until after the print.";

export function RankingsTable({
  title,
  side,
  rows,
  onSelect,
  showLegend = false,
  signalKind = "momentum",
  assetClass = "equity_large",
  upsellText,
}: {
  title: string;
  side: "long" | "short";
  rows: RankingRow[];
  onSelect: (symbol: string) => void;
  showLegend?: boolean;
  signalKind?: "momentum" | "smart_money";
  assetClass?: string;
  upsellText?: string | null;
}) {
  const accent = side === "long" ? "border-emerald-500/40" : "border-rose-500/40";
  const badge =
    side === "long"
      ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
      : "bg-rose-500/10 text-rose-300 border-rose-500/30";

  return (
    <div className={`rounded-lg border ${accent} bg-zinc-900/60 p-4`}>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold text-zinc-100">{title}</h2>
        <span className={`text-xs px-2 py-0.5 border rounded ${badge}`}>
          {side === "long" ? "LONG" : "SHORT"}
        </span>
      </div>

      {showLegend && <ScoreLegend kind={signalKind} />}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-zinc-500 text-xs uppercase tracking-wider">
            <th className="text-left font-normal py-2 w-6"></th>
            <th className="text-left font-normal py-2 w-6">#</th>
            <th className="text-left font-normal py-2">Symbol</th>
            <th className="text-right font-normal py-2">Price</th>
            <th className="text-right font-normal py-2">24h</th>
            <th className="text-right font-normal py-2">Score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <RowGroup
              key={r.symbol}
              row={r}
              index={i}
              side={side}
              onSelect={onSelect}
              assetClass={assetClass}
            />
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={6} className="py-6 text-center text-zinc-500">
                No data yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {upsellText && <ProUpsell text={upsellText} variant="inline" />}
    </div>
  );
}

function RowGroup({
  row,
  index,
  side,
  onSelect,
  assetClass,
}: {
  row: RankingRow;
  index: number;
  side: "long" | "short";
  onSelect: (symbol: string) => void;
  assetClass: string;
}) {
  const hasHeadline = Boolean(row.headline);
  const longBlockedByNews = side === "long" && row.negative_event;
  const componentEntries = row.components
    ? Object.entries(row.components).filter(([, v]) => v !== null && v !== undefined)
    : [];

  return (
    <>
      <tr
        className="border-t border-zinc-800/60 cursor-pointer hover:bg-zinc-800/30"
        onClick={() => onSelect(row.symbol)}
        title="Click for chart + headlines"
      >
        <td className="py-2" onClick={(e) => e.stopPropagation()}>
          <StarButton symbol={row.symbol} asset_class={assetClass} base={row.base} />
        </td>
        <td className="py-2 text-zinc-500">{index + 1}</td>
        <td className="py-2 text-zinc-100 font-medium">
          <span className="inline-flex items-center gap-1.5 flex-wrap">
            {row.base}
            {row.negative_event && (
              <span onClick={(e) => e.stopPropagation()}>
                <InfoBadge
                  label="NEG NEWS"
                  tone="amber"
                  size="xs"
                  explanation={NEG_NEWS_EXPLANATION}
                />
              </span>
            )}
            {row.upcoming_earnings && row.days_to_earnings !== null && (
              <span onClick={(e) => e.stopPropagation()}>
                <InfoBadge
                  label={
                    row.days_to_earnings <= 0
                      ? "EARNINGS today"
                      : `EARNINGS in ${row.days_to_earnings}d`
                  }
                  tone="zinc"
                  size="xs"
                  explanation={EARNINGS_EXPLANATION}
                />
              </span>
            )}
          </span>
        </td>
        <td className="py-2 text-right text-zinc-300 tabular-nums">
          ${formatPrice(row.price)}
        </td>
        <td className={`py-2 text-right tabular-nums ${pctColor(row.pct_change_24h)}`}>
          <span aria-hidden="true" className="text-[10px] mr-0.5">
            {directionArrow(row.pct_change_24h)}
          </span>
          {row.pct_change_24h === null
            ? "—"
            : `${row.pct_change_24h >= 0 ? "+" : ""}${row.pct_change_24h.toFixed(2)}%`}
        </td>
        <td className={`py-2 text-right tabular-nums font-medium ${scoreColor(row.score)}`}>
          {row.score >= 0 ? "+" : ""}
          {row.score.toFixed(3)}
        </td>
      </tr>

      {(hasHeadline || componentEntries.length > 0) && (
        <tr
          className="border-t border-zinc-800/30 cursor-pointer hover:bg-zinc-800/20"
          onClick={() => onSelect(row.symbol)}
        >
          <td></td>
          <td></td>
          <td colSpan={4} className="pb-2 text-[11px] leading-tight">
            {componentEntries.length > 0 && (
              <div className="text-zinc-600 mb-0.5">
                {componentEntries.map(([k, v]) => (
                  <span key={k} className="mr-3">
                    <span className="text-zinc-500">{componentLabel(k)}</span>{" "}
                    <span className="text-zinc-400 tabular-nums">
                      {formatComponent(v as number, k)}
                    </span>
                  </span>
                ))}
              </div>
            )}
            {hasHeadline && (
              <div className={longBlockedByNews ? "text-amber-300/90" : "text-zinc-500"}>
                <span className="text-zinc-600">
                  {row.headline_publisher ? `${row.headline_publisher} · ` : ""}
                  {row.news_buzz ? `${row.news_buzz} headlines · ` : ""}
                  {row.news_sentiment !== null && row.news_sentiment !== undefined
                    ? `sent ${row.news_sentiment >= 0 ? "+" : ""}${row.news_sentiment.toFixed(2)} · `
                    : ""}
                </span>
                {row.headline}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
