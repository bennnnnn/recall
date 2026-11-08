/**
 * How the composer writes a live answer: `= 5`, `= 0.3`, `= \frac{5}{6} \approx 0.8333333333`,
 * `\approx 1.414213562`. A decimal keeps 10 significant digits; one that rounded nothing away
 * (`sin 30°` is 0.49999999999999994 in floating point, shown 0.5) takes `=`, the rest `≈`.
 */
import type { LiveValue } from "@/lib/math/live/evaluate";
import { terminatingDecimal, toNumber, type Rational } from "@/lib/math/live/rational";

export type LiveAnswer = {
  /** For `MathText`: `= 5`, `\approx 1.414213562`. */
  latex: string;
  /** For a screen reader: `5`, `5/6, about 0.8333333333`. */
  spoken: string;
  /** False when the value shown is rounded. */
  exact: boolean;
};

const DIGITS = 10;
/** A whole number with more digits is written in powers of ten. */
const MAX_WHOLE_DIGITS = 15;
/** A fraction with a longer part is shown as a decimal only: it would not fit the line. */
const MAX_FRACTION_DIGITS = 6;
/** Decimals smaller than this are written in powers of ten. */
const SMALL = 1e-6;

type Decimal = { latex: string; spoken: string; plain: string };

function trimZeros(digits: string): string {
  return digits.includes(".") ? digits.replace(/0+$/, "").replace(/\.$/, "") : digits;
}

function scientific(mantissa: number, exponent: number): Decimal {
  let m = Number(mantissa.toPrecision(DIGITS));
  let e = exponent;
  if (Math.abs(m) >= 10) {
    m /= 10;
    e += 1;
  }
  const digits = trimZeros(m.toFixed(DIGITS - 1));
  return {
    latex: `${digits} \\times 10^{${e}}`,
    spoken: `${digits} × 10^${e}`,
    plain: `${digits}e${e}`,
  };
}

function decimal(x: number): Decimal {
  const size = Math.abs(x);
  if (size !== 0 && (size >= 10 ** MAX_WHOLE_DIGITS || size < SMALL)) {
    const exponent = Math.floor(Math.log10(size));
    return scientific(x / 10 ** exponent, exponent);
  }
  // Ten significant digits, never in e-notation (`toPrecision` switches to it past 1e10).
  const places = size === 0 ? 0 : Math.max(0, DIGITS - 1 - Math.floor(Math.log10(size)));
  const digits = trimZeros(x.toFixed(places));
  const plain = digits === "-0" ? "0" : digits;
  return { latex: plain, spoken: plain, plain };
}

/** Relative, so a rounded `9.536743164 × 10^{-7}` is not called exact. */
function shownExactly(x: number, shown: Decimal): boolean {
  return Math.abs(Number(shown.plain) - x) <= 1e-12 * Math.abs(x);
}

function approxAnswer(x: number): LiveAnswer {
  const shown = decimal(x);
  const exact = shownExactly(x, shown);
  return {
    latex: `${exact ? "=" : "\\approx"} ${shown.latex}`,
    spoken: exact ? shown.spoken : `≈ ${shown.spoken}`,
    exact,
  };
}

function wholeAnswer(n: bigint): LiveAnswer {
  const digits = n.toString();
  const size = digits.replace("-", "");
  if (size.length <= MAX_WHOLE_DIGITS) return { latex: `= ${digits}`, spoken: digits, exact: true };
  const mantissa = Number(`${size.slice(0, 1)}.${size.slice(1, 17)}`) * (n < 0n ? -1 : 1);
  const shown = scientific(mantissa, size.length - 1);
  return { latex: `\\approx ${shown.latex}`, spoken: `≈ ${shown.spoken}`, exact: false };
}

/**
 * `preferFraction`: the draft wrote fractions (`\frac`), so the answer is one too. A value
 * that does not end as a decimal is shown as a fraction either way. `typedFraction`: the
 * draft is that same fraction already, so only its decimal is new.
 */
function fractionAnswer(r: Rational, preferFraction: boolean, typedFraction: boolean): LiveAnswer {
  const finite = terminatingDecimal(r, DIGITS);
  const top = (r.n < 0n ? -r.n : r.n).toString();
  const bottom = r.d.toString();
  const long = top.length > MAX_FRACTION_DIGITS || bottom.length > MAX_FRACTION_DIGITS;
  if (finite && (!preferFraction || typedFraction || long)) {
    return { latex: `= ${finite}`, spoken: finite, exact: true };
  }
  const tail = approxAnswer(toNumber(r));
  if (long || typedFraction) return tail;
  const sign = r.n < 0n ? "-" : "";
  const latex = `= ${sign}\\frac{${top}}{${bottom}}`;
  const spoken = `${sign}${top}/${bottom}`;
  if (finite) return { latex: `${latex} = ${finite}`, spoken: `${spoken} = ${finite}`, exact: true };
  return { latex: `${latex} ${tail.latex}`, spoken: `${spoken}, ${tail.spoken}`, exact: true };
}

export function formatLiveValue(
  value: LiveValue,
  options: { preferFraction: boolean; typedFraction: boolean },
): LiveAnswer {
  if (value.kind === "approx") return approxAnswer(value.x);
  if (value.r.d === 1n) return wholeAnswer(value.r.n);
  return fractionAnswer(value.r, options.preferFraction, options.typedFraction);
}
