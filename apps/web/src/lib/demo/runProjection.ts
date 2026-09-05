/**
 * Fold the demo beats into an `AgentRun` snapshot at a given step.
 *
 * The output is a normal, schema-valid `AgentRun` - exactly what
 * `GET /api/runs/{runId}` returns. Nothing above this layer can tell whether it
 * came from the fixture replay or the live buyer agent, which is what makes the
 * integration swap a one-line change.
 */

import type { AgentRun, PaymentRequirement } from "@/lib/contracts/types";
import { fixtureRun, fixtureOffers, fixtureQuotes, fixturePaymentRequirement } from "./fixtures";
import {
  DEMO_BEATS,
  DEMO_STEP_COUNT,
  demoBookingsById,
  demoDecisionsById,
  demoReservationsById,
} from "./script";

export { DEMO_STEP_COUNT };

export interface DemoSnapshot {
  run: AgentRun;
  /**
   * The decoded x402 challenge, present only while the run is waiting on a
   * payment. Demo-mode only: the live API carries this as a base64 header on a
   * 402 response, which the browser never sees.
   */
  paymentChallenge?: PaymentRequirement;
  /** Presenter narration for the current beat. Not part of the contract. */
  note: string;
}

/**
 * Build the run as it looked after `step` beats (1-based).
 * `step` is clamped, so 0 gives the empty pre-run state and anything past the
 * end gives the finished run.
 */
export function projectRun(step: number): DemoSnapshot {
  const clamped = Math.max(0, Math.min(step, DEMO_STEP_COUNT));
  const beats = DEMO_BEATS.slice(0, clamped);
  const current = beats.at(-1);

  const revealed = {
    offers: false,
    quotes: false,
    plans: false,
    selectedPlan: false,
    paymentChallenge: false,
    decisions: new Set<string>(),
    reservations: new Set<string>(),
    bookings: new Set<string>(),
  };

  for (const beat of beats) {
    const { reveal } = beat;
    revealed.offers ||= reveal.offers ?? false;
    revealed.quotes ||= reveal.quotes ?? false;
    revealed.plans ||= reveal.plans ?? false;
    revealed.selectedPlan ||= reveal.selectedPlan ?? false;
    revealed.paymentChallenge ||= reveal.paymentChallenge ?? false;
    reveal.decisions?.forEach((id) => revealed.decisions.add(id));
    reveal.reservations?.forEach((id) => revealed.reservations.add(id));
    reveal.bookings?.forEach((id) => revealed.bookings.add(id));
  }

  const decisions = [...revealed.decisions]
    .map((id) => demoDecisionsById.get(id))
    .filter((decision) => decision !== undefined)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));

  const reservations = [...revealed.reservations]
    .map((id) => demoReservationsById.get(id))
    .filter((reservation) => reservation !== undefined);

  const deliveryBookings = [...revealed.bookings]
    .map((id) => demoBookingsById.get(id))
    .filter((booking) => booking !== undefined);

  const run: AgentRun = {
    runId: fixtureRun.runId,
    status: current?.status ?? "queued",
    goal: fixtureRun.goal,
    // The fixture leaves these empty; discovery fills them from the offer and
    // quote fixtures so the comparison table has something to resolve ids against.
    offers: revealed.offers ? fixtureOffers : [],
    deliveryQuotes: revealed.quotes ? fixtureQuotes : [],
    plans: revealed.plans ? fixtureRun.plans : [],
    decisions,
    reservations,
    deliveryBookings,
    spend: current?.spend ?? {
      foodDrops: "0",
      deliveryDrops: "0",
      totalDrops: "0",
      remainingDrops: fixtureRun.goal.maxTotalSpendDrops,
    },
    events: beats.map((beat) => beat.event),
    createdAt: fixtureRun.createdAt,
    updatedAt: current?.event.createdAt ?? fixtureRun.createdAt,
  };

  if (revealed.selectedPlan) {
    run.selectedPlanId = fixtureRun.selectedPlanId;
  }

  return {
    run,
    paymentChallenge: revealed.paymentChallenge ? fixturePaymentRequirement : undefined,
    note: current?.note ?? "Waiting for a procurement request.",
  };
}

/** The finished run, used by tests and by the outcome screen's static preview. */
export function projectFinalRun(): DemoSnapshot {
  return projectRun(DEMO_STEP_COUNT);
}
