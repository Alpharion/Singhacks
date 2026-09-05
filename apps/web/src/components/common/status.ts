import type { DecisionType, RunEventType, RunStatus } from "@/lib/contracts/types";
import type { Tone } from "./Badge";

/**
 * Presentation for every enum value the contract can produce.
 *
 * These maps are exhaustive on purpose. The fixture only exercises 6 of the 14
 * event types, but the live agent can emit any of them, so a missing case would
 * surface as a blank row during the demo rather than in development.
 */

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  queued: "Queued",
  parsing: "Understanding request",
  discovering: "Discovering offers",
  planning: "Building plans",
  awaiting_payment: "Awaiting payment",
  reserving: "Reserving",
  replanning: "Replanning",
  fulfilled: "Fulfilled",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const RUN_STATUS_TONE: Record<RunStatus, Tone> = {
  queued: "neutral",
  parsing: "neutral",
  discovering: "neutral",
  planning: "neutral",
  awaiting_payment: "pending",
  reserving: "settled",
  replanning: "caution",
  fulfilled: "rescue",
  failed: "rejected",
  cancelled: "rejected",
};

export const EVENT_LABEL: Record<RunEventType, string> = {
  goal_parsed: "Goal parsed",
  offers_discovered: "Offers discovered",
  offer_rejected: "Offer rejected",
  plans_built: "Plans built",
  plan_selected: "Plan selected",
  provider_failed: "Provider failed",
  replanning_started: "Replanning",
  payment_required: "Payment required",
  payment_authorized: "Payment authorised",
  payment_settled: "Payment settled",
  reservation_confirmed: "Reservation confirmed",
  delivery_confirmed: "Delivery confirmed",
  run_fulfilled: "Fulfilled",
  run_failed: "Failed",
};

export const EVENT_TONE: Record<RunEventType, Tone> = {
  goal_parsed: "neutral",
  offers_discovered: "neutral",
  offer_rejected: "rejected",
  plans_built: "neutral",
  plan_selected: "rescue",
  provider_failed: "caution",
  replanning_started: "caution",
  payment_required: "pending",
  payment_authorized: "pending",
  payment_settled: "settled",
  reservation_confirmed: "rescue",
  delivery_confirmed: "rescue",
  run_fulfilled: "rescue",
  run_failed: "rejected",
};

export const DECISION_LABEL: Record<DecisionType, string> = {
  reject_offer: "Rejected an offer",
  select_plan: "Selected a plan",
  authorize_payment: "Authorised a payment",
  replan: "Replanned",
  stop: "Stopped",
};

export const DECISION_TONE: Record<DecisionType, Tone> = {
  reject_offer: "rejected",
  select_plan: "rescue",
  authorize_payment: "settled",
  replan: "caution",
  stop: "neutral",
};

/** Human labels for the contract's 15 `ApiError.error` codes. */
export const ERROR_LABEL: Record<string, string> = {
  invalid_request: "Invalid request",
  not_found: "Not found",
  offer_expired: "Offer expired",
  offer_sold_out: "Offer sold out",
  quote_expired: "Quote expired",
  provider_unavailable: "Provider unavailable",
  budget_exceeded: "Budget exceeded",
  policy_rejected: "Blocked by policy",
  payment_required: "Payment required",
  payment_failed: "Payment failed",
  payment_timeout: "Payment timed out",
  payment_replayed: "Duplicate payment blocked",
  invoice_mismatch: "Invoice mismatch",
  network_mismatch: "Wrong network",
  internal_error: "Internal error",
};
