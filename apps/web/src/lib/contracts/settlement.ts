/**
 * Telling a real XRPL settlement apart from a simulated one.
 *
 * The buyer agent runs with `BUYER_AGENT_PAYMENT_MODE=simulated` by default, so
 * a live run can return a fully-formed, schema-valid `PaymentReceipt` for a
 * payment that never touched the ledger. Person 2 makes those receipts
 * identifiable on purpose: the transaction hash carries sixteen leading zeros,
 * which no real XRPL hash realistically does.
 *
 * The UI must not print "Validated on XRPL" over one of those. `FixtureBadge`
 * cannot cover this - it keys off the data *source*, and these arrive from the
 * live agent - so the check has to key off the receipt itself.
 *
 * See `services/buyer-agent/README.md`, "Simulated payments settle nothing".
 */

import type { AgentRun, PaymentReceipt } from "./types";
import { receiptHash } from "./types";

/** Person 2's marker: sixteen leading zeros on the transaction hash. */
const SIMULATED_HASH_PREFIX = "0".repeat(16);

/** True when this receipt is a placeholder, not evidence of XRPL settlement. */
export function isSimulatedReceipt(receipt: PaymentReceipt): boolean {
  return receiptHash(receipt).startsWith(SIMULATED_HASH_PREFIX);
}

/** Every receipt the run produced, food and delivery alike. */
export function runReceipts(run: AgentRun): PaymentReceipt[] {
  return [
    ...run.reservations.map((reservation) => reservation.paymentReceipt),
    ...run.deliveryBookings.map((booking) => booking.paymentReceipt),
  ];
}

/**
 * True when any payment in this run was simulated.
 *
 * Deliberately "any" rather than "all": a run that mixes one real settlement
 * with one placeholder must still be labelled, or the screenshot overstates
 * what happened.
 */
export function hasSimulatedSettlement(run: AgentRun): boolean {
  return runReceipts(run).some(isSimulatedReceipt);
}
