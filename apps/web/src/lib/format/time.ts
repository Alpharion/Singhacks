/**
 * Time formatting for contract timestamps.
 *
 * Every timestamp in the contract is ISO 8601 UTC. The demo narrative talks in
 * local wall-clock time ("delivered by 6 PM"), so rendering is pinned to a fixed
 * locale and time zone rather than the viewer's, otherwise the same screenshot
 * shows a different arrival time on a different laptop.
 */

const DEMO_TIME_ZONE = "Asia/Singapore";
const DEMO_LOCALE = "en-SG";

function parse(iso: string): Date {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    throw new Error(`Invalid timestamp: ${JSON.stringify(iso)}`);
  }
  return date;
}

/** `"5:35 PM"` - the form the outcome screen uses. */
export function formatClock(iso: string): string {
  return new Intl.DateTimeFormat(DEMO_LOCALE, {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: DEMO_TIME_ZONE,
  }).format(parse(iso));
}

/** `"5 Sep, 5:35 PM"` - when the date matters as well as the time. */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat(DEMO_LOCALE, {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: DEMO_TIME_ZONE,
  }).format(parse(iso));
}

/** `"07:00 - 08:30"` for a pickup window. */
export function formatWindow(window: { start: string; end: string }): string {
  return `${formatClock(window.start)} - ${formatClock(window.end)}`;
}

/**
 * Seconds between two timestamps, positive when `end` is later.
 * Used for expiry countdowns on offers and quotes.
 */
export function secondsBetween(start: string, end: string): number {
  return Math.round((parse(end).getTime() - parse(start).getTime()) / 1000);
}

/** `"in 12 min"` / `"expired"` - relative to a supplied "now" so it stays testable. */
export function formatRelative(iso: string, now: string): string {
  const seconds = secondsBetween(now, iso);
  if (seconds <= 0) return "expired";
  if (seconds < 60) return `in ${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `in ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `in ${hours}h ${remainder}m` : `in ${hours}h`;
}
