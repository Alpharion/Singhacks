import { formatXrp } from "@/lib/format/drops";
import { formatSgd, RATE_LABEL, RATE_NOTE } from "@/lib/format/money";
import { cn } from "@/lib/cn";

/**
 * An amount, shown in both currencies. Never one without the other.
 *
 * Which one leads depends on what is being described:
 *
 *   lead="sgd"  business decisions - budgets, prices, earnings, totals. A bakery owner
 *               reads dollars, not drops.
 *   lead="xrp"  settlement - payment receipts, the x402 challenge, transaction amounts.
 *               The ledger moved XRP, and a judge has to be able to check the figure
 *               against the explorer.
 *
 * Both values come from the same drops string, converted in BigInt, so they can never
 * disagree.
 */

type Lead = "sgd" | "xrp";
type Size = "sm" | "md" | "lg" | "xl";

const PRIMARY_SIZE: Record<Size, string> = {
  sm: "text-sm",
  md: "text-base",
  lg: "text-xl",
  xl: "text-3xl",
};

export function Money({
  drops,
  lead = "sgd",
  size = "md",
  className,
  tone,
}: {
  drops: string;
  lead?: Lead;
  size?: Size;
  className?: string;
  /** Tailwind text colour for the primary figure. */
  tone?: string;
}) {
  const sgd = formatSgd(drops);
  const xrp = formatXrp(drops);
  const primary = lead === "sgd" ? sgd : xrp;
  const secondary = lead === "sgd" ? xrp : sgd;

  return (
    <span className={cn("inline-flex flex-col leading-tight", className)}>
      <span
        className={cn("font-semibold tabular-nums", PRIMARY_SIZE[size], tone ?? "text-ink")}
        title={lead === "sgd" ? `${xrp} at ${RATE_LABEL}` : undefined}
      >
        {primary}
      </span>
      <span className="mt-0.5 text-[0.7rem] tabular-nums text-ink-subtle">{secondary}</span>
    </span>
  );
}

/**
 * One-line variant for dense tables, where a stacked pair would break the row rhythm.
 * Reads "S$1.80 · 0.6 XRP".
 */
export function MoneyInline({
  drops,
  lead = "sgd",
  className,
}: {
  drops: string;
  lead?: Lead;
  className?: string;
}) {
  const sgd = formatSgd(drops);
  const xrp = formatXrp(drops);

  return (
    <span className={cn("tabular-nums", className)}>
      <span className="font-medium text-ink">{lead === "sgd" ? sgd : xrp}</span>
      <span className="mx-1 text-ink-subtle">·</span>
      <span className="text-[0.72rem] text-ink-subtle">{lead === "sgd" ? xrp : sgd}</span>
    </span>
  );
}

/**
 * The footnote that keeps the conversion honest - states the rate and that it is a demo
 * assumption rather than a live quote.
 */
export function RateFootnote({ className }: { className?: string }) {
  return (
    <p className={cn("text-xs text-ink-subtle", className)}>
      Converted at {RATE_LABEL}. {RATE_NOTE}
    </p>
  );
}
