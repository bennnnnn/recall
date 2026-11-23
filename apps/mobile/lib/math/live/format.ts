/**
 * How the composer writes a live answer: `= 5`, `= 0.3`, `= \frac{5}{6} \approx 0.8333333333`,
 * `\approx 1.414213562`, `= \text{undefined}` (in the app's language). A decimal keeps 10
 * significant digits; one that rounded nothing away (`sin 30°` is 0.49999999999999994 in
 * floating point, shown 0.5) takes `=`, the rest `≈`.
 *
 * A draft with ± (`signs.ts`) shows each branch written out with its value, side by side
 * (`2 - 1 = 1,\quad 2 + 1 = 3`); with two or three signs, its distinct values
 * (`= -1,\quad 1,\quad 3`). There each value is written once, and all of a draft's values in
 * one form: fractions when the draft wrote one or a value needs one (`\frac{1}{3}`), else
 * decimals. A branch that is its value's own fraction (`-\frac{1}{3}`) gets its decimal.
 */
import type { LiveResult, LiveValue } from "@/lib/math/live/evaluate";
import { terminatingDecimal, toNumber, type Rational } from "@/lib/math/live/rational";
import type { LiveBranch } from "@/lib/math/live/signs";
import { spokenFormula } from "@/lib/math/spokenFormula";

export type LiveAnswer = {
  /** For `MathText`: `= 5`, `\approx 1.414213562`. */
  latex: string;
  /** A ± draft's branches or values: drawn at the draft's size, as they echo the draft. */
  signed: boolean;
  /** A ± draft's values alone (`= 1,\quad 3`), for branches too tall for the answer's row. */
  short?: string;
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
type Shown = Omit<LiveAnswer, "signed">;
type FormatOptions = {
  preferFraction: boolean;
  typedFraction: boolean;
  /** One form per value (a ± draft's values): `\frac{1}{3}` or `0.75`, never both. */
  compact?: boolean;
};

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

function approxAnswer(x: number): Shown {
  const shown = decimal(x);
  const exact = shownExactly(x, shown);
  return {
    latex: `${exact ? "=" : "\\approx"} ${shown.latex}`,
    spoken: exact ? shown.spoken : `≈ ${shown.spoken}`,
    exact,
  };
}

function wholeAnswer(n: bigint): Shown {
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
function fractionAnswer(r: Rational, options: FormatOptions): Shown {
  const { preferFraction, typedFraction, compact = false } = options;
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
  if (compact) return { latex, spoken, exact: true };
  if (finite) return { latex: `${latex} = ${finite}`, spoken: `${spoken} = ${finite}`, exact: true };
  return { latex: `${latex} ${tail.latex}`, spoken: `${spoken}, ${tail.spoken}`, exact: true };
}

function formatValue(value: LiveValue, options: FormatOptions): Shown {
  if (value.kind === "approx") return approxAnswer(value.x);
  if (value.r.d === 1n) return wholeAnswer(value.r.n);
  return fractionAnswer(value.r, options);
}

/** `= \text{undefined}`, the word in the app's language (`chat.math_live_undefined`). */
function formatResult(result: LiveResult, options: FormatOptions, undefinedWord: string): Shown {
  if (result.kind !== "undefined") return formatValue(result, options);
  // Plain letters: a sign with a meaning in LaTeX (`_`, `^`, a brace) is dropped.
  const word = undefinedWord.replace(/[\\{}$_^#&%~]/g, "");
  return { latex: `= \\text{${word}}`, spoken: word, exact: true };
}

const SIDE_BY_SIDE = ",\\quad ";

/** `= -1,\quad 1,\quad 3`: the first value keeps its `=`, every `≈` stays. */
const listed = (shown: Shown[]): string =>
  shown.map((s, i) => (i === 0 ? s.latex : s.latex.replace(/^= /, ""))).join(SIDE_BY_SIDE);

export function formatLiveResult(result: LiveResult, options: FormatOptions, undefinedWord: string): LiveAnswer {
  const shown = formatResult(result, options, undefinedWord);
  return { ...shown, signed: false };
}

/** A short fraction that ends as no decimal (`\frac{1}{3}`): only a fraction writes it exactly. */
function needsFraction(result: LiveResult): boolean {
  if (result.kind !== "exact" || result.r.d === 1n) return false;
  const size = (n: bigint) => (n < 0n ? -n : n).toString().length;
  const short = size(result.r.n) <= MAX_FRACTION_DIGITS && size(result.r.d) <= MAX_FRACTION_DIGITS;
  return short && terminatingDecimal(result.r, DIGITS) === null;
}

/** One form for all of a draft's values: fractions when the draft wrote one or a value needs one. */
const oneForm = (results: LiveResult[], preferFraction: boolean): FormatOptions => ({
  preferFraction: preferFraction || results.some(needsFraction),
  typedFraction: false,
  compact: true,
});

/** `2 minus 1 = 1`: the branch read out, so a listener knows which value is which. */
function spokenBranch(branch: LiveBranch, shown: Shown): string {
  const rounded = shown.spoken.startsWith("≈ ");
  return `${spokenFormula(branch.latex)} ${rounded ? "≈" : "="} ${shown.spoken.replace(/^≈ /, "")}`;
}

/** One ±: `2 - 1 = 1` and `2 + 1 = 3`, the − branch first. */
export function formatBranches(branches: LiveBranch[], preferFraction: boolean, undefinedWord: string): LiveAnswer {
  const form = oneForm(branches.map((branch) => branch.result), preferFraction);
  const shown = branches.map((branch) =>
    formatResult(branch.result, { ...form, typedFraction: branch.typed }, undefinedWord),
  );
  return {
    latex: branches.map((branch, i) => `${branch.latex} ${shown[i]!.latex}`).join(SIDE_BY_SIDE),
    signed: true,
    short: listed(shown),
    spoken: branches.map((branch, i) => spokenBranch(branch, shown[i]!)).join(", "),
    exact: shown.every((s) => s.exact),
  };
}

/** Two or three ±: the distinct values, `= -1,\quad 1,\quad 3` (`≈` kept where a value is rounded). */
/**
 * The values the display writes, each with how: two it rounds alike (`10^{20} ± 1`,
 * `1 ± 10^{-12}`) are written once, the first of them kept.
 */
function writtenValues(values: LiveValue[], preferFraction: boolean): { value: LiveValue; shown: Shown }[] {
  const form = oneForm(values, preferFraction);
  const digits = (s: Shown) => s.latex.replace(/^(?:=|\\approx) /, "");
  return values
    .map((value) => ({ value, shown: formatValue(value, form) }))
    .filter((v, i, all) => i === 0 || digits(v.shown) !== digits(all[i - 1]!.shown));
}

/** The values a draft with two or three ± shows, as the composer writes them. */
export const shownValues = (values: LiveValue[], preferFraction: boolean): LiveValue[] =>
  writtenValues(values, preferFraction).map((v) => v.value);

export function formatValues(values: LiveValue[], preferFraction: boolean): LiveAnswer {
  const shown = writtenValues(values, preferFraction).map((v) => v.shown);
  return {
    latex: listed(shown),
    signed: true,
    spoken: shown.map((s) => s.spoken).join(", "),
    exact: shown.every((s) => s.exact),
  };
}
