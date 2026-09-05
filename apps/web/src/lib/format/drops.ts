/**
 * XRP drop arithmetic and formatting.
 *
 * Every monetary value in the contract is an integer number of drops carried as
 * a decimal STRING (`"74000000"`). 1 XRP = 1,000,000 drops.
 *
 * Amounts routinely exceed what a float can represent exactly, so all arithmetic
 * here is BigInt and drops never become a `number`. Formatting is done by string
 * surgery on the digits rather than by dividing, so no rounding can creep in.
 */

export const DROPS_PER_XRP = 1_000_000n;
const DROPS_DECIMALS = 6;

const DROPS_PATTERN = /^(0|[1-9][0-9]*)$/;

/** True when `value` is a well-formed drops string per the contract's pattern. */
export function isDrops(value: string): boolean {
  return DROPS_PATTERN.test(value);
}

/**
 * Parse a contract drops string to BigInt.
 * Throws on anything malformed rather than silently yielding NaN-like garbage.
 */
export function toDrops(value: string): bigint {
  if (!isDrops(value)) {
    throw new Error(`Invalid drops value: ${JSON.stringify(value)}`);
  }
  return BigInt(value);
}

/** Serialise BigInt drops back to the contract's string form. */
export function fromDrops(drops: bigint): string {
  if (drops < 0n) throw new Error(`Drops cannot be negative: ${drops}`);
  return drops.toString();
}

/** Sum any number of drops strings without losing precision. */
export function sumDrops(...values: string[]): string {
  return fromDrops(values.reduce((total, value) => total + toDrops(value), 0n));
}

/** `a - b`, clamped at zero so a UI bar can never render negative. */
export function subtractDrops(a: string, b: string): string {
  const difference = toDrops(a) - toDrops(b);
  return fromDrops(difference > 0n ? difference : 0n);
}

/**
 * What fraction of `total` is `part`, as a 0-1 number.
 * Scales by 10,000 before converting so the ratio keeps four decimal places;
 * this is the one place a `number` is acceptable, because the result only ever
 * drives a progress bar width, never a displayed amount.
 */
export function dropsRatio(part: string, total: string): number {
  const totalDrops = toDrops(total);
  if (totalDrops === 0n) return 0;
  return Number((toDrops(part) * 10_000n) / totalDrops) / 10_000;
}

/**
 * Convert drops to a plain XRP string by moving the decimal point.
 * `"74000000"` -> `"74"`, `"600000"` -> `"0.6"`, `"1"` -> `"0.000001"`.
 * Trailing zeros are trimmed; no float ever touches the value.
 */
export function dropsToXrpString(value: string): string {
  const drops = toDrops(value);
  const digits = drops.toString().padStart(DROPS_DECIMALS + 1, "0");
  const whole = digits.slice(0, -DROPS_DECIMALS);
  const fraction = digits.slice(-DROPS_DECIMALS).replace(/0+$/, "");
  return fraction ? `${whole}.${fraction}` : whole;
}

/**
 * Human-facing XRP amount, e.g. `"74 XRP"` or `"0.6 XRP"`.
 * Group separators are applied to the whole part only.
 */
export function formatXrp(value: string, options: { suffix?: boolean } = {}): string {
  const { suffix = true } = options;
  const [whole, fraction] = dropsToXrpString(value).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const amount = fraction ? `${grouped}.${fraction}` : grouped;
  return suffix ? `${amount} XRP` : amount;
}

/** Compact form for dense tables: `74 XRP` stays, long fractions get clipped. */
export function formatXrpCompact(value: string): string {
  const [whole, fraction] = dropsToXrpString(value).split(".");
  if (!fraction) return `${whole} XRP`;
  return `${whole}.${fraction.slice(0, 2)} XRP`;
}
