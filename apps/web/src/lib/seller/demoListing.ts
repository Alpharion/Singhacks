/**
 * The demo listing, with a collection deadline that is always reachable.
 *
 * Same trap as the buyer's demo request: a fixed wall-clock deadline decays
 * through the day, and a listing whose window has already closed expires
 * instantly with nothing to watch. Six hours out is always a live window.
 */

const AGENT_TIMEZONE = "Asia/Singapore";
const LEAD_HOURS = 6;

function agentClock(moment: Date): { hour: number; minute: number } {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: AGENT_TIMEZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(moment);
  const value = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? "0");
  return { hour: value("hour") % 24, minute: value("minute") };
}

/** Always an explicit am/pm, so the parser never applies its evening rule. */
function deadlineLabel(moment: Date): string {
  const { hour, minute } = agentClock(moment);
  const roundedMinute = minute <= 30 ? 30 : 0;
  const roundedHour = minute > 30 ? (hour + 1) % 24 : hour;
  const meridiem = roundedHour < 12 ? "am" : "pm";
  const displayHour = roundedHour % 12 === 0 ? 12 : roundedHour % 12;
  return roundedMinute === 0
    ? `${displayHour} ${meridiem}`
    : `${displayHour}:${String(roundedMinute).padStart(2, "0")} ${meridiem}`;
}

export function demoListingText(now: Date = new Date()): string {
  const deadline = new Date(now.getTime() + LEAD_HOURS * 60 * 60 * 1000);
  return (
    `Sell 60 vegetarian bakery meal boxes, collection by ${deadlineLabel(deadline)}, ` +
    "asking 2 XRP each but no less than 1.20 XRP."
  );
}
