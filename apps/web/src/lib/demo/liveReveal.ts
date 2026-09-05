/**
 * Reveal a live run one beat at a time.
 *
 * The buyer agent finishes a simulated run in well under a second - all
 * nineteen events land on the same timestamp - so the dashboard would snap
 * straight from empty to finished and there would be nothing to watch or narrate.
 *
 * This does not invent anything. Every field comes from the real `AgentRun`;
 * the only thing being decided here is *when* each piece appears, so a viewer
 * can follow the agent's reasoning in the order it actually happened. Once the
 * last event is revealed the output is the untouched run.
 *
 * Fixture mode has its own richer replay in `runProjection.ts`, driven by the
 * scripted demo beats. This is the live counterpart, driven by whatever the
 * agent really did.
 */

import type { AgentRun, RunEventType, RunStatus } from "@/lib/contracts/types";
import { subtractDrops, sumDrops } from "@/lib/format/drops";
import type { DemoSnapshot } from "./runProjection";

/** The run status implied by the most recent revealed event. */
const STATUS_AFTER: Record<RunEventType, RunStatus> = {
  goal_parsed: "parsing",
  offers_discovered: "discovering",
  offer_rejected: "discovering",
  plans_built: "planning",
  plan_selected: "planning",
  provider_failed: "replanning",
  replanning_started: "replanning",
  payment_required: "awaiting_payment",
  payment_authorized: "awaiting_payment",
  payment_settled: "reserving",
  reservation_confirmed: "reserving",
  delivery_confirmed: "reserving",
  run_fulfilled: "fulfilled",
  run_failed: "failed",
};

/** Events that correspond to the agent recording a decision. */
const DECISION_EVENTS: ReadonlySet<RunEventType> = new Set<RunEventType>([
  "offer_rejected",
  "plan_selected",
  "payment_authorized",
  "replanning_started",
  "run_failed",
]);

function countOf(types: RunEventType[], predicate: (type: RunEventType) => boolean): number {
  return types.filter(predicate).length;
}

/**
 * The run as it looked after `revealed` of its events.
 *
 * `revealed` is clamped, so 0 gives the pre-run state and anything at or past
 * the event count gives the run exactly as the agent returned it.
 */
export function revealRun(run: AgentRun, revealed: number): DemoSnapshot {
  const total = run.events.length;
  const count = Math.max(0, Math.min(revealed, total));

  // Fully revealed: hand back the real object, so nothing downstream is ever
  // looking at a reconstruction once the run is done.
  if (count >= total) return { run, note: "" };

  const events = run.events.slice(0, count);
  const seen = events.map((event) => event.eventType);
  const latest = events.at(-1);

  const has = (type: RunEventType) => seen.includes(type);

  // Reservations and bookings appear as their confirmations do.
  const reservations = run.reservations.slice(
    0,
    countOf(seen, (type) => type === "reservation_confirmed"),
  );
  const deliveryBookings = run.deliveryBookings.slice(
    0,
    countOf(seen, (type) => type === "delivery_confirmed"),
  );
  const decisions = run.decisions.slice(0, countOf(seen, (type) => DECISION_EVENTS.has(type)));

  // Spend is recomputed from what has actually been paid for so far, so the
  // budget bar fills as the money is committed rather than jumping at the end.
  const foodDrops = sumDrops(
    ...reservations.map((reservation) => reservation.paymentReceipt.amountDrops),
  );
  const deliveryDrops = sumDrops(
    ...deliveryBookings.map((booking) => booking.paymentReceipt.amountDrops),
  );
  const totalDrops = sumDrops(foodDrops, deliveryDrops);

  const revealedRun: AgentRun = {
    ...run,
    status: latest ? STATUS_AFTER[latest.eventType] : "queued",
    offers: has("offers_discovered") ? run.offers : [],
    deliveryQuotes: has("offers_discovered") ? run.deliveryQuotes : [],
    plans: has("plans_built") ? run.plans : [],
    decisions,
    reservations,
    deliveryBookings,
    spend: {
      foodDrops,
      deliveryDrops,
      totalDrops,
      remainingDrops: subtractDrops(run.goal.maxTotalSpendDrops, totalDrops),
    },
    events,
    updatedAt: latest?.createdAt ?? run.createdAt,
  };

  if (!has("plan_selected")) delete revealedRun.selectedPlanId;
  // A failure is only news once the failing event has been shown.
  if (!has("run_failed")) delete revealedRun.failure;

  return { run: revealedRun, note: "" };
}
