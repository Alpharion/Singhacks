import { describe, expect, it } from "vitest";
import agentRun from "@/lib/demo/fixtures/agent-run.json";
import {
  dropsRatio,
  dropsToXrpString,
  formatXrp,
  formatXrpCompact,
  isDrops,
  subtractDrops,
  sumDrops,
  toDrops,
} from "./drops";

describe("drops parsing", () => {
  it("accepts contract-shaped values", () => {
    expect(isDrops("0")).toBe(true);
    expect(isDrops("74000000")).toBe(true);
  });

  it("rejects anything the contract would not emit", () => {
    for (const bad of ["", "01", "-1", "1.5", "1e6", " 1", "abc"]) {
      expect(isDrops(bad)).toBe(false);
      expect(() => toDrops(bad)).toThrow();
    }
  });

  it("keeps precision beyond what a float can hold", () => {
    // 2^53 drops + 1: a Number round-trip would lose the trailing digit.
    const huge = "9007199254740993";
    expect(toDrops(huge).toString()).toBe(huge);
    expect(sumDrops(huge, "1")).toBe("9007199254740994");
  });
});

describe("drops to XRP", () => {
  it("moves the decimal point without dividing", () => {
    expect(dropsToXrpString("74000000")).toBe("74");
    expect(dropsToXrpString("600000")).toBe("0.6");
    expect(dropsToXrpString("1")).toBe("0.000001");
    expect(dropsToXrpString("0")).toBe("0");
    expect(dropsToXrpString("120000000")).toBe("120");
  });

  it("formats for display", () => {
    expect(formatXrp("74000000")).toBe("74 XRP");
    expect(formatXrp("74000000", { suffix: false })).toBe("74");
    expect(formatXrp("1234000000")).toBe("1,234 XRP");
    expect(formatXrpCompact("650000")).toBe("0.65 XRP");
  });
});

describe("drops arithmetic", () => {
  it("clamps subtraction at zero", () => {
    expect(subtractDrops("10", "4")).toBe("6");
    expect(subtractDrops("4", "10")).toBe("0");
  });

  it("computes a ratio for progress bars", () => {
    expect(dropsRatio("74000000", "120000000")).toBeCloseTo(0.6166, 3);
    expect(dropsRatio("0", "0")).toBe(0);
  });
});

describe("the frozen fixture's own invariants", () => {
  const { spend, goal, plans } = agentRun;
  const selected = plans.find((plan) => plan.planId === agentRun.selectedPlanId)!;

  it("food + delivery equals total spend", () => {
    expect(sumDrops(spend.foodDrops, spend.deliveryDrops)).toBe(spend.totalDrops);
  });

  it("spent + remaining equals the delegated budget", () => {
    expect(sumDrops(spend.totalDrops, spend.remainingDrops)).toBe(goal.maxTotalSpendDrops);
  });

  it("the selected plan's allocations sum to its food cost", () => {
    const lines = selected.foodAllocations.map((a) => a.lineTotalDrops);
    expect(sumDrops(...lines)).toBe(selected.foodCostDrops);
  });

  it("the selected plan's allocations sum to the requested meal count", () => {
    const meals = selected.foodAllocations.reduce((n, a) => n + a.quantity, 0);
    expect(meals).toBe(selected.totalMeals);
    expect(meals).toBe(goal.mealCount);
  });

  it("renders the numbers the demo script quotes", () => {
    expect(formatXrp(spend.foodDrops)).toBe("62 XRP");
    expect(formatXrp(spend.deliveryDrops)).toBe("12 XRP");
    expect(formatXrp(spend.totalDrops)).toBe("74 XRP");
    expect(formatXrp(goal.maxTotalSpendDrops)).toBe("120 XRP");
  });
});
