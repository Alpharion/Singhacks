/**
 * Fiat display for XRP amounts.
 *
 * The people this product serves - a community-kitchen procurement manager, a bakery
 * owner - do not think in XRP. They think in dollars. So every business figure on screen
 * leads in SGD, with the XRP amount kept alongside it because that is what the ledger
 * actually moved.
 *
 * The contract never changes: amounts stay drops strings end to end. This module converts
 * for display only, and does it in BigInt so no float ever touches a monetary value.
 */

import { toDrops, DROPS_PER_XRP, formatXrp as formatXrpFromDrops } from "./drops";

/**
 * Indicative rate, held as integer cents per XRP rather than a float - same reason drops
 * are strings. One place to change.
 *
 * This is a fixed demo assumption, not a live quote, and the UI labels it as such. A
 * production build would read the rate from the XRPL Price Oracle (XLS-47, enabled on
 * mainnet) rather than hardcoding it, keeping the whole system XRPL-native instead of
 * depending on an external price API.
 */
export const SGD_CENTS_PER_XRP = 300n; // S$3.00 / XRP
export const RATE_LABEL = "S$3.00 / XRP";
export const RATE_NOTE =
  "Indicative demo rate. Production reads the XRPL Price Oracle (XLS-47).";

export const CURRENCY_CODE = "SGD";
export const CURRENCY_SYMBOL = "S$";

const CENTS_PER_DOLLAR = 100n;

/**
 * Convert drops to whole SGD cents, rounded half-up.
 *
 * `drops x centsPerXrp / 1_000_000`, with half a unit added before the divide so the
 * result rounds rather than truncating. All integer - no rounding drift can accumulate.
 */
export function dropsToSgdCents(value: string): bigint {
  const drops = toDrops(value);
  const numerator = drops * SGD_CENTS_PER_XRP;
  return (numerator + DROPS_PER_XRP / 2n) / DROPS_PER_XRP;
}

/** `"74000000"` -> `"S$222.00"`. Always two decimal places, grouped thousands. */
export function formatSgd(value: string, options: { symbol?: boolean } = {}): string {
  const { symbol = true } = options;
  const cents = dropsToSgdCents(value);
  const dollars = cents / CENTS_PER_DOLLAR;
  const remainder = cents % CENTS_PER_DOLLAR;
  const grouped = dollars.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const amount = `${grouped}.${remainder.toString().padStart(2, "0")}`;
  return symbol ? `${CURRENCY_SYMBOL}${amount}` : amount;
}

/**
 * Both currencies as one string: `"S$1.80 · 0.6 XRP"`.
 *
 * For dense table cells where a stacked pair would break the row rhythm, and for the
 * handful of helper components that take a plain string rather than a node.
 */
export function formatDual(value: string, lead: "sgd" | "xrp" = "sgd"): string {
  const sgd = formatSgd(value);
  const xrp = formatXrpFromDrops(value);
  return lead === "sgd" ? `${sgd} · ${xrp}` : `${xrp} · ${sgd}`;
}

/**
 * Per-unit price for a line of goods, e.g. cost per meal.
 * Divides in cents so the result is still exact to the cent.
 */
export function formatSgdPerUnit(value: string, units: number): string {
  if (units <= 0) return formatSgd("0");
  const cents = dropsToSgdCents(value) / BigInt(units);
  const dollars = cents / CENTS_PER_DOLLAR;
  const remainder = cents % CENTS_PER_DOLLAR;
  return `${CURRENCY_SYMBOL}${dollars}.${remainder.toString().padStart(2, "0")}`;
}
