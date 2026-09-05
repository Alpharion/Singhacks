/**
 * Friendly aliases over the generated contract types.
 *
 * `generated.ts` names schemas after their source filenames
 * (`components["schemas"]["agent-run.schema"]`), which is unpleasant to read at
 * every call site. Import from here instead.
 *
 * Source of truth: packages/contracts (Contract Freeze v1.0.0, owned by Person 4).
 */

import type { components } from "./generated";

type Schemas = components["schemas"];

// --- Core domain -----------------------------------------------------------

export type AgentRun = Schemas["agent-run.schema"];
export type ProcurementGoal = Schemas["procurement-goal.schema"];
export type ProcurementRequest = Schemas["procurement-request.schema"];
export type FoodOffer = Schemas["food-offer.schema"];
export type FoodOffersResponse = Schemas["food-offers-response.schema"];
export type DeliveryQuote = Schemas["delivery-quote.schema"];
export type DeliveryQuotesResponse = Schemas["delivery-quotes-response.schema"];
export type ProcurementPlan = Schemas["procurement-plan.schema"];
export type AgentDecision = Schemas["agent-decision.schema"];
export type PurchaseIntent = Schemas["purchase-intent.schema"];
export type PaymentReceipt = Schemas["payment-receipt.schema"];
export type Reservation = Schemas["reservation.schema"];
export type DeliveryBooking = Schemas["delivery-booking.schema"];
export type ApiError = Schemas["api-error.schema"];

// --- Primitives ------------------------------------------------------------

export type Identifier = Schemas["Identifier"];
export type Drops = Schemas["Drops"];
export type PositiveDrops = Schemas["PositiveDrops"];
export type XrplAddress = Schemas["XrplAddress"];
export type TransactionHash = Schemas["TransactionHash"];
export type DietaryTag = Schemas["DietaryTag"];
export type TimeWindow = Schemas["TimeWindow"];
export type GeoLocation = Schemas["Location"];

// --- Derived pieces the contract nests inline ------------------------------

export type RunStatus = Schemas["RunStatus"];
export type RunEvent = AgentRun["events"][number];
export type RunEventType = RunEvent["eventType"];
export type RunSpend = AgentRun["spend"];
export type FoodAllocation = ProcurementPlan["foodAllocations"][number];
export type RejectedAlternative = AgentDecision["rejectedAlternatives"][number];
export type DecisionType = AgentDecision["decisionType"];
export type PolicySnapshot = PurchaseIntent["policySnapshot"];

/**
 * The decoded x402 `PAYMENT-REQUIRED` challenge.
 *
 * Hand-written on purpose: the header travels as base64 over the wire, so
 * `payment-requirement.schema.json` is never referenced from `openapi.yaml` and
 * the generator has nothing to emit. Kept in sync with that schema by hand.
 * The schema sets `additionalProperties: true` for x402 forward-compatibility.
 */
export interface PaymentRequirement {
  x402Version: 2;
  accepts: PaymentRequirementAccept[];
  [key: string]: unknown;
}

export interface PaymentRequirementAccept {
  scheme: "exact";
  network: "xrpl:1";
  asset: "XRP";
  payTo: XrplAddress;
  /** Drops. Note the bare name - it is `amount` here, `amountDrops` everywhere else. */
  amount: PositiveDrops;
  maxTimeoutSeconds: number;
  extra: {
    invoiceId: string;
    sourceTag: number;
    destinationTag?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

// --- Status helpers --------------------------------------------------------

/** Runs in these states will not change again, so polling can stop. */
export const TERMINAL_RUN_STATUSES = ["fulfilled", "failed", "cancelled"] as const;

export function isTerminalStatus(status: RunStatus): boolean {
  return (TERMINAL_RUN_STATUSES as readonly string[]).includes(status);
}

// --- Field-name traps ------------------------------------------------------
// The contract spells the same transaction hash two different ways. Route every
// read through these so a rename in one place cannot silently blank the UI.

/** `PaymentReceipt.transaction` - note: not `transactionHash`. */
export function receiptHash(receipt: PaymentReceipt): TransactionHash {
  return receipt.transaction;
}

/** `AgentDecision.transactionHash` - present only once a payment has settled. */
export function decisionHash(decision: AgentDecision): TransactionHash | undefined {
  return decision.transactionHash;
}

/**
 * Explorer links are supplied by the backend as complete URIs. Never build one
 * from a hash in the frontend - the network prefix is the backend's call.
 */
export function explorerUrl(receipt: PaymentReceipt): string {
  return receipt.explorerUrl;
}
