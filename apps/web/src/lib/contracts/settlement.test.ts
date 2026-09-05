import { describe, expect, it } from "vitest";
import agentRun from "@/lib/demo/fixtures/agent-run.json";
import paymentReceipt from "@/lib/demo/fixtures/payment-receipt.json";
import type { AgentRun, PaymentReceipt } from "./types";
import { hasSimulatedSettlement, isSimulatedReceipt, runReceipts } from "./settlement";

const realReceipt = paymentReceipt as PaymentReceipt;

/** A receipt shaped exactly as the buyer agent emits one in simulated mode. */
function simulatedReceipt(): PaymentReceipt {
  return {
    ...realReceipt,
    transaction: `${"0".repeat(16)}1E69F51CFA4D63453E85F6021A2E1368684A87EA811BD250`,
    explorerUrl:
      "http://localhost:8001/api/simulated/00000000000000001E69F51CFA4D63453E85F6021A2E1368684A87EA811BD250",
  };
}

describe("isSimulatedReceipt", () => {
  it("flags the agent's sixteen-leading-zero placeholder", () => {
    expect(isSimulatedReceipt(simulatedReceipt())).toBe(true);
  });

  it("leaves a real settlement alone", () => {
    expect(isSimulatedReceipt(realReceipt)).toBe(false);
  });

  it("does not flag a hash that merely starts with a few zeros", () => {
    // Fifteen zeros is a hash a real ledger could plausibly produce.
    const nearMiss = {
      ...realReceipt,
      transaction: `${"0".repeat(15)}B1E69F51CFA4D63453E85F6021A2E1368684A87EA811BD25`,
    } as PaymentReceipt;
    expect(isSimulatedReceipt(nearMiss)).toBe(false);
  });
});

describe("hasSimulatedSettlement", () => {
  const run = agentRun as AgentRun;

  it("collects receipts from reservations and bookings alike", () => {
    expect(runReceipts(run)).toHaveLength(
      run.reservations.length + run.deliveryBookings.length,
    );
  });

  it("is false for the frozen fixture run", () => {
    expect(hasSimulatedSettlement(run)).toBe(false);
  });

  it("is true when even one payment was simulated", () => {
    const mixed: AgentRun = {
      ...run,
      reservations: run.reservations.map((reservation, index) =>
        index === 0
          ? { ...reservation, paymentReceipt: simulatedReceipt() }
          : reservation,
      ),
    };
    expect(hasSimulatedSettlement(mixed)).toBe(true);
  });
});
