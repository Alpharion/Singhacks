import { CheckCircle2 } from "lucide-react";
import type { AgentRun } from "@/lib/contracts/types";
import { explorerUrl, receiptHash } from "@/lib/contracts/types";
import { formatXrp } from "@/lib/format/drops";
import { formatClock } from "@/lib/format/time";
import { ExplorerLink } from "@/components/common/Xrpl";
import { FixtureBadge } from "@/components/common/FixtureBadge";

/**
 * The closing screen from the demo script (PROJECT_CONTEXT.md section 14).
 *
 * Shown only once the run is fulfilled. Deliberately the loudest thing on the
 * page, because it is the answer to "so what did the agent actually achieve".
 */
export function OutcomeSummary({ run }: { run: AgentRun }) {
  if (run.status !== "fulfilled") return null;

  const mealsSecured = run.reservations
    .filter((reservation) => reservation.status === "confirmed")
    .reduce((total, reservation) => total + reservation.quantity, 0);

  const arrival = run.deliveryBookings.at(0)?.deliveryEta;

  const receipts = [
    ...run.reservations.map((reservation) => reservation.paymentReceipt),
    ...run.deliveryBookings.map((booking) => booking.paymentReceipt),
  ];

  return (
    <section className="animate-beat-in overflow-hidden rounded-panel border border-rescue/35 bg-rescue-dim/25">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-rescue/20 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <CheckCircle2 className="size-5 text-rescue" aria-hidden />
          <h2 className="text-base font-semibold text-ink">
            {mealsSecured} {run.goal.dietaryTags.join(" / ")} meals secured
          </h2>
        </div>
        <FixtureBadge />
      </header>

      <div className="grid gap-x-6 gap-y-5 px-5 py-5 sm:grid-cols-2 lg:grid-cols-4">
        <Figure label="Food cost" value={formatXrp(run.spend.foodDrops)} />
        <Figure label="Delivery cost" value={formatXrp(run.spend.deliveryDrops)} />
        <Figure label="Total spent" value={formatXrp(run.spend.totalDrops)} tone />
        <Figure
          label="Unspent authority"
          value={formatXrp(run.spend.remainingDrops)}
          hint={`of ${formatXrp(run.goal.maxTotalSpendDrops)}`}
        />
        {arrival && <Figure label="Expected arrival" value={formatClock(arrival)} />}
        <Figure label="Food rescued" value={`${mealsSecured} meals`} tone />
        <Figure
          label="Providers paid"
          value={`${receipts.length}`}
          hint="sellers and couriers"
        />
        <Figure
          label="Deadline"
          value={formatClock(run.goal.deliveryDeadline)}
          hint="met with time to spare"
        />
      </div>

      <div className="border-t border-rescue/20 px-5 py-4">
        <h3 className="text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle">
          XRPL transactions
        </h3>
        <ul className="mt-2.5 space-y-1.5">
          {receipts.map((receipt) => (
            <li key={receiptHash(receipt)} className="flex items-center gap-3 text-xs">
              <span className="w-20 shrink-0 tabular-nums text-ink-muted">
                {formatXrp(receipt.amountDrops)}
              </span>
              <ExplorerLink url={explorerUrl(receipt)} hash={receiptHash(receipt)} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Figure({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: boolean;
}) {
  return (
    <div className="min-w-0">
      <div className="text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle">
        {label}
      </div>
      <div
        className={`mt-1 text-2xl font-semibold tabular-nums ${tone ? "text-rescue" : "text-ink"}`}
      >
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-ink-subtle">{hint}</div>}
    </div>
  );
}
