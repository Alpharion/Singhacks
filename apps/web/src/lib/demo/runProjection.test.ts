import { describe, expect, it } from "vitest";
import { isTerminalStatus } from "@/lib/contracts/types";
import { sumDrops } from "@/lib/format/drops";
import { fixtureRun } from "./fixtures";
import { DEMO_BEATS, DEMO_STEP_COUNT } from "./script";
import { projectFinalRun, projectRun } from "./runProjection";

const ALL_EVENT_TYPES = new Set([
  "goal_parsed",
  "offers_discovered",
  "offer_rejected",
  "plans_built",
  "plan_selected",
  "provider_failed",
  "replanning_started",
  "payment_required",
  "payment_authorized",
  "payment_settled",
  "reservation_confirmed",
  "delivery_confirmed",
  "run_fulfilled",
  "run_failed",
]);

const everyStep = Array.from({ length: DEMO_STEP_COUNT }, (_, i) => i + 1);

describe("the demo script", () => {
  it("uses only event types the contract allows", () => {
    for (const beat of DEMO_BEATS) {
      expect(ALL_EVENT_TYPES.has(beat.event.eventType)).toBe(true);
    }
  });

  it("numbers events contiguously from 1, as the contract validator requires", () => {
    DEMO_BEATS.forEach((beat, index) => {
      expect(beat.event.sequence).toBe(index + 1);
    });
  });

  it("never lets spend exceed the delegated budget", () => {
    for (const beat of DEMO_BEATS) {
      expect(sumDrops(beat.spend.totalDrops, beat.spend.remainingDrops)).toBe(
        fixtureRun.goal.maxTotalSpendDrops,
      );
    }
  });

  it("tells the story the demo script calls for", () => {
    const types = DEMO_BEATS.map((beat) => beat.event.eventType);
    expect(types).toContain("offer_rejected");
    expect(types).toContain("provider_failed");
    expect(types).toContain("replanning_started");
    expect(types).toContain("payment_required");
    expect(types).toContain("payment_settled");
    expect(types.at(-1)).toBe("run_fulfilled");
  });
});

describe("projectRun", () => {
  it("starts empty before any beat has played", () => {
    const { run } = projectRun(0);
    expect(run.status).toBe("queued");
    expect(run.events).toHaveLength(0);
    expect(run.offers).toHaveLength(0);
    expect(run.spend.totalDrops).toBe("0");
    expect(run.spend.remainingDrops).toBe(fixtureRun.goal.maxTotalSpendDrops);
  });

  it("clamps out-of-range steps instead of throwing", () => {
    expect(projectRun(-5).run.events).toHaveLength(0);
    expect(projectRun(999).run.status).toBe("fulfilled");
  });

  it.each(everyStep)("emits a contract-valid run at step %i", (step) => {
    const { run } = projectRun(step);

    // Events stay contiguous at every intermediate step.
    run.events.forEach((event, index) => expect(event.sequence).toBe(index + 1));
    expect(run.events).toHaveLength(step);

    // The budget identity holds throughout, not just at the end.
    expect(sumDrops(run.spend.totalDrops, run.spend.remainingDrops)).toBe(
      fixtureRun.goal.maxTotalSpendDrops,
    );
    expect(sumDrops(run.spend.foodDrops, run.spend.deliveryDrops)).toBe(run.spend.totalDrops);

    // Required array fields are always present, never undefined.
    for (const key of [
      "offers",
      "deliveryQuotes",
      "plans",
      "decisions",
      "reservations",
      "deliveryBookings",
    ] as const) {
      expect(Array.isArray(run[key])).toBe(true);
    }

    // A selected plan id, when present, must name a plan that exists.
    if (run.selectedPlanId) {
      expect(run.plans.map((plan) => plan.planId)).toContain(run.selectedPlanId);
    }

    // Decisions arrive in chronological order.
    const timestamps = run.decisions.map((decision) => decision.createdAt);
    expect(timestamps).toEqual([...timestamps].sort());
  });

  it("only reaches a terminal status on the final step", () => {
    for (const step of everyStep.slice(0, -1)) {
      expect(isTerminalStatus(projectRun(step).run.status)).toBe(false);
    }
    expect(isTerminalStatus(projectFinalRun().run.status)).toBe(true);
  });

  it("reveals data progressively rather than all at once", () => {
    expect(projectRun(1).run.offers).toHaveLength(0);
    expect(projectRun(2).run.offers).toHaveLength(3);
    expect(projectRun(2).run.deliveryQuotes).toHaveLength(2);
    expect(projectRun(3).run.plans).toHaveLength(0);
    expect(projectRun(4).run.plans).toHaveLength(2);
    expect(projectRun(4).run.selectedPlanId).toBeUndefined();
    expect(projectRun(5).run.selectedPlanId).toBe("plan_final_001");
  });

  it("spends nothing until a payment has actually settled", () => {
    for (const step of everyStep.filter((s) => s < 10)) {
      expect(projectRun(step).run.spend.totalDrops).toBe("0");
    }
    expect(projectRun(10).run.spend.totalDrops).toBe("36000000");
  });

  it("exposes the x402 challenge only while awaiting payment", () => {
    expect(projectRun(7).paymentChallenge).toBeUndefined();
    expect(projectRun(8).paymentChallenge?.x402Version).toBe(2);
    expect(projectRun(8).paymentChallenge?.accepts[0].amount).toBe("36000000");
  });
});

describe("the final projection matches the frozen fixture", () => {
  const { run } = projectFinalRun();

  it("ends on the fixture's own spend figures", () => {
    expect(run.spend).toEqual(fixtureRun.spend);
  });

  it("ends with the fixture's reservations and bookings", () => {
    expect(run.reservations).toEqual(fixtureRun.reservations);
    expect(run.deliveryBookings).toEqual(fixtureRun.deliveryBookings);
  });

  it("ends on the fixture's status and selected plan", () => {
    expect(run.status).toBe(fixtureRun.status);
    expect(run.selectedPlanId).toBe(fixtureRun.selectedPlanId);
  });

  it("includes every decision the fixture carries", () => {
    const ids = run.decisions.map((decision) => decision.decisionId);
    for (const decision of fixtureRun.decisions) {
      expect(ids).toContain(decision.decisionId);
    }
  });
});
