import { Check } from "lucide-react";
import type { AgentRun, ProcurementPlan } from "@/lib/contracts/types";
import { formatDual, formatSgd } from "@/lib/format/money";
import { Money } from "@/components/common/Money";
import { formatClock } from "@/lib/format/time";
import { Badge } from "@/components/common/Badge";
import { EmptyState } from "@/components/common/Panel";
import { cn } from "@/lib/cn";

/**
 * The competing plans, side by side.
 *
 * No single seller has 100 meals, so each plan is a combination. Showing both
 * is the point: it makes the agent's choice legible as an economic decision
 * rather than an arbitrary pick.
 */
export function PlanComparison({ run }: { run: AgentRun }) {
  if (run.plans.length === 0) {
    return <EmptyState>The agent has not worked out the combinations yet.</EmptyState>;
  }

  const sellerNameFor = (offerId: string) =>
    run.offers.find((offer) => offer.offerId === offerId)?.sellerName ?? offerId;

  const courierNameFor = (quoteId: string) =>
    run.deliveryQuotes.find((quote) => quote.quoteId === quoteId)?.providerName ?? quoteId;

  const cheapest = run.plans.reduce((best, plan) =>
    BigInt(plan.totalCostDrops) < BigInt(best.totalCostDrops) ? plan : best,
  );

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {run.plans.map((plan) => (
        <PlanCard
          key={plan.planId}
          plan={plan}
          isSelected={plan.planId === run.selectedPlanId}
          isCheapest={plan.planId === cheapest.planId}
          budgetDrops={run.goal.maxTotalSpendDrops}
          sellerNameFor={sellerNameFor}
          courierName={courierNameFor(plan.deliveryQuoteId)}
        />
      ))}
    </div>
  );
}

function PlanCard({
  plan,
  isSelected,
  isCheapest,
  budgetDrops,
  sellerNameFor,
  courierName,
}: {
  plan: ProcurementPlan;
  isSelected: boolean;
  isCheapest: boolean;
  budgetDrops: string;
  sellerNameFor: (offerId: string) => string;
  courierName: string;
}) {
  const withinBudget = BigInt(plan.totalCostDrops) <= BigInt(budgetDrops);

  return (
    <article
      className={cn(
        "rounded-xl border p-4 transition-colors",
        isSelected ? "border-rescue/50 bg-rescue-dim/30" : "border-border bg-canvas",
      )}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <code className="font-mono text-xs text-ink-subtle">{plan.planId}</code>
          <div className="mt-1.5">
            <Money
              drops={plan.totalCostDrops}
              size="xl"
              tone={isSelected ? "text-rescue" : "text-ink"}
            />
          </div>
        </div>
        {isSelected && (
          <Badge tone="rescue">
            <Check className="size-3" aria-hidden />
            Selected
          </Badge>
        )}
      </header>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {isCheapest && <Badge tone="settled">Lowest cost</Badge>}
        {withinBudget ? (
          <Badge tone="neutral">Within budget</Badge>
        ) : (
          <Badge tone="rejected">Over budget</Badge>
        )}
        {plan.feasible ? null : <Badge tone="rejected">Infeasible</Badge>}
      </div>

      <dl className="mt-4 space-y-1.5 text-sm">
        <Line label="Food" value={formatDual(plan.foodCostDrops)} />
        <Line label="Delivery" value={formatDual(plan.deliveryCostDrops)} />
        <Line label="Meals" value={`${plan.totalMeals}`} />
        <Line label="Arrives" value={formatClock(plan.expectedDeliveryAt)} />
        <Line label="Risk score" value={plan.riskScore.toFixed(1)} />
      </dl>

      <div className="mt-4 border-t border-border pt-3">
        <h4 className="text-[0.62rem] uppercase tracking-[0.08em] text-ink-subtle">
          Allocation
        </h4>
        <ul className="mt-2 space-y-1.5">
          {plan.foodAllocations.map((allocation) => (
            <li
              key={allocation.offerId}
              className="flex items-baseline justify-between gap-3 text-xs"
            >
              <span className="truncate text-ink-muted">
                {sellerNameFor(allocation.offerId)}
              </span>
              <span className="shrink-0 tabular-nums text-ink">
                {allocation.quantity} × {formatSgd(allocation.unitPriceDrops)}
              </span>
            </li>
          ))}
          <li className="flex items-baseline justify-between gap-3 text-xs">
            <span className="truncate text-ink-muted">{courierName}</span>
            <span className="shrink-0 tabular-nums text-ink">
              {formatDual(plan.deliveryCostDrops)}
            </span>
          </li>
        </ul>
      </div>

      {plan.rejectionReasons.length > 0 && (
        <ul className="mt-3 space-y-1 rounded-lg bg-rejected-dim/60 px-2.5 py-2 text-xs text-rejected">
          {plan.rejectionReasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </article>
  );
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-ink-subtle">{label}</dt>
      <dd className="tabular-nums text-ink">{value}</dd>
    </div>
  );
}
