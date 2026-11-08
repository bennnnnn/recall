/**
 * Exact fractions for the composer's live answer (`lib/math/live/answer.ts`): `0.1 + 0.2` is
 * `3/10`, never `0.30000000000000004`. Every value is reduced with a positive denominator.
 * Sizes are capped so a keystroke never waits on a huge number: past the cap a result is
 * `null` and the caller falls back to a decimal (or shows no answer).
 */

export type Rational = { readonly n: bigint; readonly d: bigint };

/** About 300 digits: past this the answer is shown as a decimal. */
const MAX_BITS = 1000;

function abs(value: bigint): bigint {
  return value < 0n ? -value : value;
}

function gcd(a: bigint, b: bigint): bigint {
  let x = abs(a);
  let y = abs(b);
  while (y !== 0n) [x, y] = [y, x % y];
  return x;
}

export function bitLength(value: bigint): number {
  return abs(value).toString(2).length;
}

function tooBig(value: Rational): boolean {
  return bitLength(value.n) > MAX_BITS || bitLength(value.d) > MAX_BITS;
}

/** `n/d` reduced; `null` for a zero denominator or a value past the size cap. */
export function rational(n: bigint, d: bigint = 1n): Rational | null {
  if (d === 0n) return null;
  const sign = d < 0n ? -1n : 1n;
  const divisor = gcd(n, d) || 1n;
  const value = { n: (sign * n) / divisor, d: (sign * d) / divisor };
  return tooBig(value) ? null : value;
}

/** `"12.5"` → 25/2, `".5"` → 1/2; anything else `null`. */
export function parseDecimal(text: string): Rational | null {
  const match = /^(\d*)(?:\.(\d+))?$/.exec(text);
  if (!match || (!match[1] && !match[2])) return null;
  const places = match[2] ?? "";
  return rational(BigInt((match[1] || "0") + places), 10n ** BigInt(places.length));
}

export const add = (a: Rational, b: Rational) => rational(a.n * b.d + b.n * a.d, a.d * b.d);
export const sub = (a: Rational, b: Rational) => rational(a.n * b.d - b.n * a.d, a.d * b.d);
export const mul = (a: Rational, b: Rational) => rational(a.n * b.n, a.d * b.d);
export const div = (a: Rational, b: Rational) => rational(a.n * b.d, a.d * b.n);

export function isInteger(value: Rational): boolean {
  return value.d === 1n;
}

export function toNumber(value: Rational): number {
  return Number(value.n) / Number(value.d);
}

/** `a^k` for a whole `k`; `null` for `0^-k` or a result past the size cap. */
export function powInteger(base: Rational, k: bigint): Rational | null {
  if (k === 0n) return rational(1n);
  const exponent = abs(k);
  const bits = Math.max(bitLength(base.n), bitLength(base.d));
  if (bits * Number(exponent) > MAX_BITS + 64) return null;
  const n = base.n ** exponent;
  const d = base.d ** exponent;
  return k > 0n ? rational(n, d) : rational(d, n);
}

/** The whole `k`th root of a non-negative whole number, when there is one. */
function integerRoot(value: bigint, k: bigint): bigint | null {
  if (value < 2n) return value;
  // Newton's method from above, on whole numbers.
  let x = 1n << BigInt(Math.ceil(bitLength(value) / Number(k)) + 1);
  for (;;) {
    const next = ((k - 1n) * x + value / x ** (k - 1n)) / k;
    if (next >= x) break;
    x = next;
  }
  return x ** k === value ? x : null;
}

/** The exact real `k`th root (`k` ≥ 2), when it is a fraction; `null` otherwise. */
export function rootExact(value: Rational, k: bigint): Rational | null {
  if (k < 2n) return null;
  const negative = value.n < 0n;
  if (negative && k % 2n === 0n) return null;
  const n = integerRoot(abs(value.n), k);
  const d = integerRoot(value.d, k);
  if (n === null || d === null) return null;
  return rational(negative ? -n : n, d);
}

/** `floor(a)` as a whole number. */
export function floor(value: Rational): bigint {
  const q = value.n / value.d;
  return value.n < 0n && q * value.d !== value.n ? q - 1n : q;
}

/** The decimal digits of an exact value, when it ends within `maxPlaces` places. */
export function terminatingDecimal(value: Rational, maxPlaces: number): string | null {
  let d = value.d;
  let twos = 0;
  let fives = 0;
  while (d % 2n === 0n) {
    d /= 2n;
    twos += 1;
  }
  while (d % 5n === 0n) {
    d /= 5n;
    fives += 1;
  }
  const places = Math.max(twos, fives);
  if (d !== 1n || places > maxPlaces) return null;
  const scaled = abs(value.n) * 10n ** BigInt(places) / value.d;
  const digits = scaled.toString().padStart(places + 1, "0");
  const whole = digits.slice(0, digits.length - places);
  const fraction = digits.slice(digits.length - places);
  return `${value.n < 0n ? "-" : ""}${whole}${places ? `.${fraction}` : ""}`;
}
