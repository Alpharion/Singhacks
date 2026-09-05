import { Clock, Leaf, ShieldCheck, Wallet } from "lucide-react";
import type { ProcurementGoal, PolicySnapshot } from "@/lib/contracts/types";
import { formatXrp } from "@/lib/format/drops";
import { formatClock } from "@/lib/format/time";
import { XrplAddr } from "@/components/common/Xrpl";

/**
 * What the human is delegating.
 *
 * This is the difference between an agentic payment and a checkout: the person
 * sets the boundary, the agent chooses the individual purchases inside it. The
 * caps here are enforced by deterministic policy code, not by the model.
 */
export function AuthorityCard({
  goal,
  policy,
}: {
  goal: ProcurementGoal;
  policy: PolicySnapshot;
}) {
  const rows = [
    {
      icon: Wallet,
      label: "Total budget",
      value: formatXrp(goal.maxTotalSpendDrops),
      detail: `Max ${formatXrp(policy.maxTransactionSpendDrops)} in any single transaction`,
    },
    {
      icon: Clock,
      label: "Deliver by",
      value: formatClock(goal.deliveryDeadline),
      detail: `${goal.destination.zone}${goal.destination.addressLine ? ` · ${goal.destination.addressLine}` : ""}`,
    },
    {
      icon: Leaf,
      label: "Dietary policy",
      // Only this row is title-cased: `capitalize` would turn "6:00 pm" into
      // "6:00 Pm" on the row above.
      value: goal.dietaryTags
        .map((tag) => tag.replace(/_/g, " "))
        .map((tag) => tag[0].toUpperCase() + tag.slice(1))
        .join(", "),
      detail: `${goal.mealCount} meals · min reliability ${(goal.minSellerReliability * 100).toFixed(0)}%`,
    },
  ];

  return (
    <div className="space-y-4">
      <dl className="space-y-3.5">
        {rows.map(({ icon: Icon, label, value, detail }) => (
          <div key={label} className="flex gap-3">
            <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-surface-raised ring-1 ring-inset ring-border">
              <Icon className="size-3.5 text-ink-muted" aria-hidden />
            </span>
            <div className="min-w-0">
              <dt className="text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle">
                {label}
              </dt>
              <dd className="mt-0.5 text-sm font-medium text-ink">{value}</dd>
              <dd className="mt-0.5 text-xs text-ink-subtle">{detail}</dd>
            </div>
          </div>
        ))}
      </dl>

      <div className="rounded-lg border border-border bg-canvas/60 p-3.5">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-3.5 text-rescue" aria-hidden />
          <span className="text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle">
            Payable only to
          </span>
        </div>
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {policy.allowedPayees.map((payee) => (
            <li
              key={payee}
              className="rounded-md bg-surface-raised px-2 py-1 ring-1 ring-inset ring-border"
            >
              <XrplAddr address={payee} />
            </li>
          ))}
        </ul>
        <p className="mt-2.5 text-xs leading-relaxed text-ink-subtle">
          A payment to any other address is refused by the policy layer before the wallet is
          asked to sign. The language model never holds a key.
        </p>
      </div>
    </div>
  );
}
