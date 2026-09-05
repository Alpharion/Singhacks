/**
 * The demo narrative.
 *
 * `fixtures/agent-run.json` is a *finished* run - status `fulfilled`, everything
 * paid. The demo (PROJECT_CONTEXT.md section 14) needs the journey instead:
 * discovery, a rejection, a provider dropping out, a replan, an HTTP 402, then
 * settlement.
 *
 * So this file expands the fixture's six events into the thirteen beats that
 * story actually has, and records what becomes visible at each one. Everything
 * it adds is drawn from the fixture's own data - no invented sellers, prices,
 * hashes, or reasons. The three `AgentDecision`s are used verbatim; the only
 * authored decision is the `select_plan` step, which the fixture omits.
 *
 * Invariants preserved from the contract:
 *   - `sequence` is contiguous from 1
 *   - every `eventType` is one of the 14 allowed values
 *   - the final beat's data is byte-equal to the fixture's end state
 */

import type { AgentDecision, RunEvent, RunSpend, RunStatus } from "@/lib/contracts/types";
import { fixtureRun } from "./fixtures";
import { subtractDrops, sumDrops } from "@/lib/format/drops";

const BUDGET = fixtureRun.goal.maxTotalSpendDrops;

const reservationsById = new Map(
  fixtureRun.reservations.map((reservation) => [reservation.reservationId, reservation]),
);
const bookingsById = new Map(
  fixtureRun.deliveryBookings.map((booking) => [booking.bookingId, booking]),
);
const decisionsById = new Map(
  fixtureRun.decisions.map((decision) => [decision.decisionId, decision]),
);

/** Spend after paying `amounts` for food and `delivery` for couriers. */
function spendAfter(food: string[], delivery: string[]): RunSpend {
  const foodDrops = food.length ? sumDrops(...food) : "0";
  const deliveryDrops = delivery.length ? sumDrops(...delivery) : "0";
  const totalDrops = sumDrops(foodDrops, deliveryDrops);
  return {
    foodDrops,
    deliveryDrops,
    totalDrops,
    remainingDrops: subtractDrops(BUDGET, totalDrops),
  };
}

const BAKERY_FOOD = "36000000";
const HOTEL_FOOD = "26000000";
const COURIER_DELIVERY = "12000000";

/**
 * The `select_plan` decision the fixture does not carry.
 * Its numbers come straight from the two plans in the fixture: the selected plan
 * costs 74 XRP against the alternative's 74.5 XRP.
 */
const selectPlanDecision: AgentDecision = {
  decisionId: "decision_select_001",
  runId: fixtureRun.runId,
  decisionType: "select_plan",
  objective: "Choose the cheapest feasible plan that still meets the 6 PM deadline.",
  selectedOptionId: "plan_final_001",
  alternativesConsidered: ["plan_final_001", "plan_alt_001"],
  reasons: [
    "Both plans supply all 100 vegetarian meals and arrive before the deadline.",
    "plan_final_001 costs 74 XRP against 74.5 XRP, leaving more budget for a courier fallback.",
  ],
  rejectedAlternatives: [
    {
      optionId: "plan_alt_001",
      reasons: ["Costs 0.5 XRP more for the same meals and the same arrival time."],
    },
  ],
  remainingBudgetDrops: BUDGET,
  walletPolicyId: fixtureRun.goal.walletPolicyId,
  createdAt: "2026-09-05T06:01:00Z",
};

/** Everything the UI knows at a given point in the story. */
export interface DemoBeat {
  event: RunEvent;
  status: RunStatus;
  spend: RunSpend;
  /** Narration for the presenter - not part of the contract. */
  note: string;
  reveal: {
    offers?: boolean;
    quotes?: boolean;
    plans?: boolean;
    selectedPlan?: boolean;
    /** x402 challenge is a demo-mode extra; the live API does not expose it. */
    paymentChallenge?: boolean;
    decisions?: string[];
    reservations?: string[];
    bookings?: string[];
  };
}

function event(
  sequence: number,
  eventType: RunEvent["eventType"],
  message: string,
  createdAt: string,
  relatedId?: string,
): RunEvent {
  return relatedId
    ? { sequence, eventType, message, relatedId, createdAt }
    : { sequence, eventType, message, createdAt };
}

const NOTHING_SPENT = spendAfter([], []);

export const DEMO_BEATS: DemoBeat[] = [
  {
    event: event(
      1,
      "goal_parsed",
      "Parsed a request for 100 vegetarian meals before 6 PM within 120 XRP.",
      "2026-09-05T06:00:05Z",
      "goal_demo_001",
    ),
    status: "parsing",
    spend: NOTHING_SPENT,
    note: "The manager typed one sentence. The agent turned it into hard constraints.",
    reveal: {},
  },
  {
    event: event(
      2,
      "offers_discovered",
      "Found 3 seller offers and 2 courier quotes across 3 zones.",
      "2026-09-05T06:00:15Z",
    ),
    status: "discovering",
    spend: NOTHING_SPENT,
    note: "Discovery is free. Nothing has been paid for yet.",
    reveal: { offers: true, quotes: true },
  },
  {
    event: event(
      3,
      "offer_rejected",
      "Rejected Central Grill because it is not vegetarian.",
      "2026-09-05T06:00:30Z",
      "offer_grill_001",
    ),
    status: "planning",
    spend: NOTHING_SPENT,
    note: "The cheapest offer on the board, refused on a dietary rule the agent cannot override.",
    reveal: { decisions: ["decision_reject_001"] },
  },
  {
    event: event(
      4,
      "plans_built",
      "Built 2 feasible multi-seller plans covering all 100 meals.",
      "2026-09-05T06:00:50Z",
    ),
    status: "planning",
    spend: NOTHING_SPENT,
    note: "No single seller has 100 meals, so the agent combines two.",
    reveal: { plans: true },
  },
  {
    event: event(
      5,
      "plan_selected",
      "Selected plan_final_001 at 74 XRP, 0.5 XRP cheaper than the alternative.",
      "2026-09-05T06:01:00Z",
      "plan_final_001",
    ),
    status: "planning",
    spend: NOTHING_SPENT,
    note: "An economic decision, explained: cheaper for the same meals and the same arrival.",
    reveal: { selectedPlan: true, decisions: ["decision_select_001"] },
  },
  {
    event: event(
      6,
      "provider_failed",
      "Economy Van became unavailable before booking.",
      "2026-09-05T06:01:20Z",
      "quote_economy_001",
    ),
    status: "replanning",
    spend: NOTHING_SPENT,
    note: "The failure the demo is built around. Nothing has been paid, so nothing is lost.",
    reveal: {},
  },
  {
    event: event(
      7,
      "replanning_started",
      "Replanning delivery with the remaining valid courier quote.",
      "2026-09-05T06:01:21Z",
      "quote_fast_001",
    ),
    status: "replanning",
    spend: NOTHING_SPENT,
    note: "Recovery without human intervention, still inside the delegated budget.",
    reveal: { decisions: ["decision_replan_001"] },
  },
  {
    event: event(
      8,
      "payment_required",
      "Green Oven Bakery returned HTTP 402 with x402 payment requirements.",
      "2026-09-05T06:02:00Z",
      "offer_bakery_001",
    ),
    status: "awaiting_payment",
    spend: NOTHING_SPENT,
    note: "This is x402: the price arrives as an HTTP 402, machine to machine.",
    reveal: { paymentChallenge: true },
  },
  {
    event: event(
      9,
      "payment_authorized",
      "Policy checks passed: approved payee, under the per-transaction cap, invoice unique.",
      "2026-09-05T06:02:20Z",
      "offer_bakery_001",
    ),
    status: "awaiting_payment",
    spend: NOTHING_SPENT,
    note: "Deterministic code authorises. The language model never signs anything.",
    reveal: { decisions: ["decision_payment_001"] },
  },
  {
    event: event(
      10,
      "payment_settled",
      "XRPL payment validated for the bakery reservation.",
      "2026-09-05T06:02:30Z",
      "offer_bakery_001",
    ),
    status: "reserving",
    spend: spendAfter([BAKERY_FOOD], []),
    note: "Settled on XRPL. The hash is the receipt.",
    reveal: { reservations: ["reservation_bakery_001"] },
  },
  {
    event: event(
      11,
      "reservation_confirmed",
      "Both food reservations confirmed: 60 meals from the bakery, 40 from the hotel.",
      "2026-09-05T06:03:31Z",
    ),
    status: "reserving",
    spend: spendAfter([BAKERY_FOOD, HOTEL_FOOD], []),
    note: "Payment bought something real: an exclusive hold on the inventory.",
    reveal: { reservations: ["reservation_bakery_001", "reservation_hotel_001"] },
  },
  {
    event: event(
      12,
      "delivery_confirmed",
      "FastRoute Courier booked for pickup at 08:00, arriving 09:35.",
      "2026-09-05T06:04:31Z",
      "quote_fast_001",
    ),
    status: "reserving",
    spend: spendAfter([BAKERY_FOOD, HOTEL_FOOD], [COURIER_DELIVERY]),
    note: "Three payments, three providers, one delegated budget.",
    reveal: { bookings: ["booking_fast_001"] },
  },
  {
    event: event(
      13,
      "run_fulfilled",
      "100 vegetarian meals and delivery are confirmed within budget.",
      "2026-09-05T06:04:31Z",
      fixtureRun.runId,
    ),
    status: "fulfilled",
    spend: spendAfter([BAKERY_FOOD, HOTEL_FOOD], [COURIER_DELIVERY]),
    note: "74 XRP of a 120 XRP authority. 46 XRP never left the wallet.",
    reveal: {},
  },
];

export const DEMO_STEP_COUNT = DEMO_BEATS.length;

/** Decisions keyed by id, including the one authored above. */
export const demoDecisionsById = new Map<string, AgentDecision>([
  ...decisionsById,
  [selectPlanDecision.decisionId, selectPlanDecision],
]);

export { reservationsById as demoReservationsById, bookingsById as demoBookingsById };
