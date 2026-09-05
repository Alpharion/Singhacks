import type { AgentRun } from "@/lib/contracts/types";
import { dropsRatio, formatXrp } from "@/lib/format/drops";
import { formatClock } from "@/lib/format/time";
import { Badge, Stat } from "@/components/common/Badge";
import { RUN_STATUS_LABEL, RUN_STATUS_TONE } from "@/components/common/status";
import { cn } from "@/lib/cn";

/**
 * The always-visible top bar: what was asked for, what state the agent is in,
 * and how much of the delegated budget has actually been committed.
 */
export function RunHeader({ run }: { run: AgentRun }) {
  const { goal, spend, status } = run;
  const spentRatio = dropsRatio(spend.totalDrops, goal.maxTotalSpendDrops);
  const isLive = !["fulfilled", "failed", "cancelled"].includes(status);

  const mealsSecured = run.reservations
    .filter((reservation) => reservation.status === "confirmed")
    .reduce((total, reservation) => total + reservation.quantity, 0);

  return (
    <div className="rounded-panel border border-border bg-surface/80 backdrop-blur-sm">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-5 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <Badge tone={RUN_STATUS_TONE[status]}>
              <span
                className={cn(
                  "size-1.5 rounded-full bg-current",
                  isLive && "animate-pulse",
                )}
                aria-hidden
              />
              {RUN_STATUS_LABEL[status]}
            </Badge>
            <code className="font-mono text-xs text-ink-subtle">{run.runId}</code>
          </div>
          <p className="mt-2.5 max-w-3xl text-[0.95rem] leading-relaxed text-ink">
            {goal.mealCount} {goal.dietaryTags.join(" / ")} meals to {goal.destination.zone},
            delivered by {formatClock(goal.deliveryDeadline)}, within{" "}
            {formatXrp(goal.maxTotalSpendDrops)}.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-5 px-5 py-4 sm:grid-cols-4">
        <Stat
          label="Meals secured"
          value={`${mealsSecured} / ${goal.mealCount}`}
          tone={mealsSecured >= goal.mealCount ? "rescue" : undefined}
          hint={mealsSecured >= goal.mealCount ? "Target met" : "Reserved so far"}
        />
        <Stat
          label="Committed"
          value={formatXrp(spend.totalDrops)}
          tone="settled"
          hint={`Food ${formatXrp(spend.foodDrops, { suffix: false })} · delivery ${formatXrp(spend.deliveryDrops, { suffix: false })}`}
        />
        <Stat
          label="Remaining"
          value={formatXrp(spend.remainingDrops)}
          hint={`of ${formatXrp(goal.maxTotalSpendDrops)} authorised`}
        />
        <div className="col-span-2 sm:col-span-1">
          <div className="text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle">
            Budget used
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-raised">
            <div
              className="h-full rounded-full bg-settled transition-[width] duration-700 ease-out"
              style={{ width: `${Math.min(spentRatio * 100, 100)}%` }}
            />
          </div>
          <div className="mt-1.5 text-xs tabular-nums text-ink-subtle">
            {(spentRatio * 100).toFixed(1)}% of authority
          </div>
        </div>
      </div>
    </div>
  );
}
