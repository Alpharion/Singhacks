import {
  Ban,
  CheckCircle2,
  CircleDollarSign,
  FileSearch,
  Layers,
  PackageCheck,
  Radar,
  RefreshCw,
  Sparkles,
  Target,
  Truck,
  TriangleAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { RunEvent, RunEventType } from "@/lib/contracts/types";
import { formatClock } from "@/lib/format/time";
import { EVENT_LABEL, EVENT_TONE } from "@/components/common/status";
import { EmptyState } from "@/components/common/Panel";
import { cn } from "@/lib/cn";

/** Exhaustive: the live agent can emit any of the contract's 14 event types. */
const EVENT_ICON: Record<RunEventType, LucideIcon> = {
  goal_parsed: Sparkles,
  offers_discovered: Radar,
  offer_rejected: Ban,
  plans_built: Layers,
  plan_selected: Target,
  provider_failed: TriangleAlert,
  replanning_started: RefreshCw,
  payment_required: FileSearch,
  payment_authorized: CircleDollarSign,
  payment_settled: CheckCircle2,
  reservation_confirmed: PackageCheck,
  delivery_confirmed: Truck,
  run_fulfilled: CheckCircle2,
  run_failed: XCircle,
};

const TONE_TEXT = {
  neutral: "text-ink-muted",
  rescue: "text-rescue",
  settled: "text-settled",
  caution: "text-caution",
  rejected: "text-rejected",
  pending: "text-pending",
} as const;

const TONE_RING = {
  neutral: "bg-surface-raised ring-border",
  rescue: "bg-rescue-dim ring-rescue/30",
  settled: "bg-settled-dim ring-settled/30",
  caution: "bg-caution-dim ring-caution/30",
  rejected: "bg-rejected-dim ring-rejected/30",
  pending: "bg-pending-dim ring-pending/30",
} as const;

/**
 * The agent's activity log, newest last.
 *
 * Keyed by `sequence` so React animates only the beat that just arrived rather
 * than re-running the entrance animation for the whole list.
 */
export function AgentTimeline({ events }: { events: RunEvent[] }) {
  if (events.length === 0) {
    return <EmptyState>The agent has not started yet.</EmptyState>;
  }

  const latest = events.at(-1);

  return (
    <ol className="relative space-y-0">
      {events.map((event) => {
        const tone = EVENT_TONE[event.eventType];
        const Icon = EVENT_ICON[event.eventType];
        const isLatest = event.sequence === latest?.sequence;
        const isLast = event === events.at(-1);

        return (
          <li key={event.sequence} className="animate-beat-in relative flex gap-3.5 pb-5">
            {!isLast && (
              <span
                className="absolute left-[15px] top-8 bottom-0 w-px bg-border"
                aria-hidden
              />
            )}

            <span
              className={cn(
                "relative z-10 grid size-8 shrink-0 place-items-center rounded-full ring-1 ring-inset",
                TONE_RING[tone],
                isLatest && tone === "settled" && "animate-pulse-ring",
              )}
            >
              <Icon className={cn("size-4", TONE_TEXT[tone])} aria-hidden />
            </span>

            <div className="min-w-0 flex-1 pt-1">
              <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                <span className={cn("text-sm font-semibold", TONE_TEXT[tone])}>
                  {EVENT_LABEL[event.eventType]}
                </span>
                <time
                  dateTime={event.createdAt}
                  className="font-mono text-[0.7rem] tabular-nums text-ink-subtle"
                >
                  {formatClock(event.createdAt)}
                </time>
              </div>
              <p className="mt-1 text-sm leading-relaxed text-ink-muted">{event.message}</p>
              {event.relatedId && (
                <code className="mt-1.5 inline-block rounded bg-surface-raised px-1.5 py-0.5 font-mono text-[0.68rem] text-ink-subtle">
                  {event.relatedId}
                </code>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
