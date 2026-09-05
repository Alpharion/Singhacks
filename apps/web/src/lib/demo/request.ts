/**
 * The demo request, with a deadline that is always reachable.
 *
 * The frozen fixture asks for delivery "by 6 PM". That is a wall-clock time, so
 * the request quietly rots as the day goes on: the agent parses it to 18:00
 * local, and a courier needing ~3h35m to collect and deliver cannot make it
 * once the afternoon is half gone. The run then fails with "no courier can
 * collect", which is a correct answer to an impossible request - and a broken
 * demo.
 *
 * Fixture discovery has the same problem from the other end. It rebases the
 * frozen timestamps onto the parsed deadline, so a deadline less than about
 * four hours out lands the courier quotes' expiry in the past.
 *
 * Both are fixed by asking for a deadline that is always a comfortable distance
 * away. Six hours clears the courier's ~3h35m and the fixtures' ~3h50m with
 * room to spare, at any hour of any day.
 */

import { fixtureProcurementRequest } from "./fixtures";

/** The zone the buyer agent reads wall-clock phrases in (SURPLUSFLOW_TIMEZONE). */
const AGENT_TIMEZONE = "Asia/Singapore";

const DEMO_LEAD_HOURS = 6;

/** Matches the "by 6 PM" clause, mirroring the agent's own DEADLINE_CLOCK. */
const DEADLINE_CLAUSE = /\bby\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?/i;

/**
 * `hh:mm` in the agent's timezone, whatever the browser's own zone is. The
 * label has to mean the same thing to the parser as it does on screen.
 */
function agentClock(moment: Date): { hour: number; minute: number } {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: AGENT_TIMEZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(moment);

  const value = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? "0");
  // "24" is how en-GB spells midnight in this format.
  return { hour: value("hour") % 24, minute: value("minute") };
}

/**
 * A deadline the parser reads back exactly as written: always an explicit
 * am/pm, so its "a bare early hour means the evening" rule never applies.
 */
function deadlineLabel(moment: Date): string {
  const { hour, minute } = agentClock(moment);

  // Round up to the next half hour so the request reads like something a person
  // would actually say.
  const roundedMinute = minute <= 30 ? 30 : 0;
  const roundedHour = minute > 30 ? (hour + 1) % 24 : hour;

  const meridiem = roundedHour < 12 ? "am" : "pm";
  const displayHour = roundedHour % 12 === 0 ? 12 : roundedHour % 12;

  return roundedMinute === 0
    ? `${displayHour} ${meridiem}`
    : `${displayHour}:${String(roundedMinute).padStart(2, "0")} ${meridiem}`;
}

/**
 * The frozen demo request with its deadline moved to a reachable time.
 *
 * Everything else - the meal count, the diet, the destination, the budget - is
 * the contract fixture verbatim, so the run still reproduces the frozen plan.
 */
export function demoRequestText(now: Date = new Date()): string {
  const deadline = new Date(now.getTime() + DEMO_LEAD_HOURS * 60 * 60 * 1000);
  const label = `by ${deadlineLabel(deadline)}`;

  const text = fixtureProcurementRequest.requestText;
  return DEADLINE_CLAUSE.test(text) ? text.replace(DEADLINE_CLAUSE, label) : text;
}
