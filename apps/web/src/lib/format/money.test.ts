import { describe, expect, it } from "vitest";
import agentRun from "@/lib/demo/fixtures/agent-run.json";
import foodOffers from "@/lib/demo/fixtures/food-offers.json";
import { dropsToSgdCents, formatSgd, formatSgdPerUnit } from "./money";
import { sumDrops } from "./drops";

describe("drops to SGD", () => {
  it("converts the figures the demo quotes", () => {
    expect(formatSgd("120000000")).toBe("S$360.00"); // 120 XRP budget
    expect(formatSgd("74000000")).toBe("S$222.00"); // 74 XRP spent
    expect(formatSgd("46000000")).toBe("S$138.00"); // 46 XRP unspent
    expect(formatSgd("62000000")).toBe("S$186.00"); // food
    expect(formatSgd("12000000")).toBe("S$36.00"); // delivery
  });

  it("converts unit prices", () => {
    expect(formatSgd("600000")).toBe("S$1.80"); // bakery box
    expect(formatSgd("650000")).toBe("S$1.95"); // hotel bowl
    expect(formatSgd("400000")).toBe("S$1.20"); // grill box
    expect(formatSgd("500000")).toBe("S$1.50"); // seller floor
  });

  it("handles zero and groups thousands", () => {
    expect(formatSgd("0")).toBe("S$0.00");
    expect(formatSgd("1000000000")).toBe("S$3,000.00");
    expect(formatSgd("74000000", { symbol: false })).toBe("222.00");
  });

  it("rounds half-up rather than truncating", () => {
    // 1 drop = 0.0003 cents, rounds to 0.
    expect(dropsToSgdCents("1")).toBe(0n);
    // 1667 drops = 0.5001 cents, rounds to 1.
    expect(dropsToSgdCents("1667")).toBe(1n);
    // 1666 drops = 0.4998 cents, rounds to 0.
    expect(dropsToSgdCents("1666")).toBe(0n);
  });

  it("keeps precision on values a float would mangle", () => {
    // Well beyond Number.MAX_SAFE_INTEGER once multiplied by the rate.
    const huge = "9007199254740993";
    expect(dropsToSgdCents(huge)).toBe(2702159776422n);
  });

  it("rejects malformed drops rather than guessing", () => {
    for (const bad of ["", "1.5", "-1", "1e6", "abc"]) {
      expect(() => dropsToSgdCents(bad)).toThrow();
    }
  });
});

describe("per-unit pricing", () => {
  it("gives the cost per rescued meal", () => {
    // 74 XRP across 100 meals.
    expect(formatSgdPerUnit(agentRun.spend.totalDrops, 100)).toBe("S$2.22");
    // Food alone.
    expect(formatSgdPerUnit(agentRun.spend.foodDrops, 100)).toBe("S$1.86");
  });

  it("does not divide by zero", () => {
    expect(formatSgdPerUnit("74000000", 0)).toBe("S$0.00");
  });
});

describe("the fixtures land in believable territory", () => {
  it("prices every offer as a plausible surplus meal", () => {
    for (const offer of foodOffers.offers) {
      const cents = dropsToSgdCents(offer.unitPriceDrops);
      // A surplus meal between 50 cents and 10 dollars.
      expect(cents).toBeGreaterThanOrEqual(50n);
      expect(cents).toBeLessThanOrEqual(1000n);
    }
  });

  it("keeps the budget identity intact in dollars", () => {
    const { spend, goal } = agentRun;
    expect(formatSgd(sumDrops(spend.totalDrops, spend.remainingDrops))).toBe(
      formatSgd(goal.maxTotalSpendDrops),
    );
    expect(formatSgd(sumDrops(spend.foodDrops, spend.deliveryDrops))).toBe(
      formatSgd(spend.totalDrops),
    );
  });
});
