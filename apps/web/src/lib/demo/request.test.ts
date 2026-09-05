import { describe, expect, it } from "vitest";
import { demoRequestText } from "./request";
import { fixtureProcurementRequest } from "./fixtures";

/** The agent's own DEADLINE_CLOCK, ported (services/buyer-agent/.../parsing.py). */
const DEADLINE_CLOCK = /\b(?:by|before|no later than)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b/i;

/**
 * The agent's `_deadline_from_clock`, ported: resolve the label against a
 * reference instant, rolling to tomorrow once the time has passed.
 */
function resolveDeadline(text: string, reference: Date): Date {
  const match = DEADLINE_CLOCK.exec(text);
  if (!match) throw new Error(`no deadline clause in: ${text}`);

  let hour = Number(match[1]);
  const minute = Number(match[2] ?? 0);
  const meridiem = match[3]?.toLowerCase();

  if (meridiem === "pm" && hour !== 12) hour += 12;
  else if (meridiem === "am" && hour === 12) hour = 0;
  else if (!meridiem && hour < 7 && match[2] === undefined) hour += 12;

  const candidate = new Date(reference);
  candidate.setHours(hour, minute, 0, 0);
  if (candidate.getTime() <= reference.getTime()) {
    candidate.setDate(candidate.getDate() + 1);
  }
  return candidate;
}

describe("demoRequestText", () => {
  it("keeps every constraint but the deadline", () => {
    const text = demoRequestText(new Date("2026-09-05T08:47:00Z"));
    expect(text).toContain("100 vegetarian meals");
    expect(text).toContain("Queenstown");
    expect(text).toContain("120 XRP");
    // Only the deadline clause differs from the frozen fixture.
    const strip = (value: string) => value.replace(DEADLINE_CLOCK, "by <deadline>");
    expect(strip(text)).toBe(strip(fixtureProcurementRequest.requestText));
  });

  it("always states an explicit am/pm", () => {
    // A bare early hour would trip the agent's "6 means the evening" rule.
    for (let hour = 0; hour < 24; hour += 1) {
      const text = demoRequestText(new Date(Date.UTC(2026, 8, 5, hour, 17)));
      expect(DEADLINE_CLOCK.exec(text)?.[3]).toMatch(/am|pm/i);
    }
  });

  /**
   * The regression this file exists for. The courier needs ~3h35m and the
   * rebased fixture quotes expire ~3h50m before the deadline, so a demo request
   * is only viable if its deadline is at least four hours out - at every hour
   * of the day, not just the ones we happened to rehearse at.
   */
  it("leaves at least four hours to deliver, at every hour and minute tested", () => {
    for (let hour = 0; hour < 24; hour += 1) {
      for (const minute of [0, 17, 29, 30, 31, 45, 59]) {
        const now = new Date(2026, 8, 5, hour, minute, 0, 0);
        const deadline = resolveDeadline(demoRequestText(now), now);
        const hoursAhead = (deadline.getTime() - now.getTime()) / 3_600_000;
        expect(
          hoursAhead,
          `at ${hour}:${String(minute).padStart(2, "0")} the deadline was only ${hoursAhead.toFixed(2)}h away`,
        ).toBeGreaterThanOrEqual(4);
      }
    }
  });

  it("is the fixture text that would have failed", () => {
    // Guards the premise: the frozen request really is unreachable in the
    // afternoon, which is why this module exists.
    const afternoon = new Date(2026, 8, 5, 16, 47);
    const deadline = resolveDeadline(fixtureProcurementRequest.requestText, afternoon);
    const hoursAhead = (deadline.getTime() - afternoon.getTime()) / 3_600_000;
    expect(hoursAhead).toBeLessThan(4);
  });
});
