import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type Tone = "neutral" | "rescue" | "settled" | "caution" | "rejected" | "pending";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface-raised text-ink-muted ring-border-strong",
  rescue: "bg-rescue-dim text-rescue ring-rescue/40",
  settled: "bg-settled-dim text-settled ring-settled/40",
  caution: "bg-caution-dim text-caution ring-caution/40",
  rejected: "bg-rejected-dim text-rejected ring-rejected/40",
  pending: "bg-pending-dim text-pending ring-pending/40",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** A small labelled figure - the unit the header and outcome screens are built from. */
export function Stat({
  label,
  value,
  hint,
  tone,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  const valueTone =
    tone === "rescue"
      ? "text-rescue"
      : tone === "settled"
        ? "text-settled"
        : tone === "caution"
          ? "text-caution"
          : tone === "rejected"
            ? "text-rejected"
            : "text-ink";

  return (
    <div className={cn("min-w-0", className)}>
      <div className="text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle">
        {label}
      </div>
      <div className={cn("mt-1 text-xl font-semibold tabular-nums", valueTone)}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-subtle">{hint}</div>}
    </div>
  );
}
