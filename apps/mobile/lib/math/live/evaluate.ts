/**
 * Works out a calculation `read.ts` read, for the composer's live answer.
 *
 * A value stays an exact fraction while every step allows it (+ − × ÷, whole powers, perfect
 * roots, %, !, |x|, mod, logs that come out whole); π, e, trig, other logs and other roots
 * give a decimal. A value with no number at all is undefined, as the server says it is: a zero
 * divisor (`1 ÷ 0`, `0 ÷ 0`, `0^{-1}`), a pole (`tan 90°`, `cot 0°`, `coth 0`), a log of zero, a
 * log to base 1. `5 mod 0` and `\frac{1}{0}` are undefined on the phone only: the turn does not
 * verify them yet (SymPy's `Mod(5, 0)` raises). Only a zero that is exactly zero makes one: a decimal that
 * rounded to 0 (`10^{-400}`) is a number too small to hold, and shows nothing; a trig value
 * that is a fraction at exact degrees is exact (`2 sin 30° − 1` is 0). An undefined
 * part carries through + − × and a numerator (`2 + 1 ÷ 0` is undefined, as SymPy's zoo is);
 * anywhere else the phone stays cautious and shows nothing: there SymPy sometimes gives a value
 * back (`1 ÷ tan 90°` is 0 to it, `|1 ÷ 0|` an infinity, `(1 ÷ 0)^0` 1), and the turn verifies
 * none of them. `0^0` is 1, as
 * SymPy and the server read it. Anything else the server would not call one real number gives
 * no value: a root or a log of a negative (complex numbers are the server's), an infinity
 * (`atanh 1`), `50 + 10%` (55 or 50.1), a number too big.
 *
 * Angles follow the server's reading: `30^{\circ}` is degrees, an angle with π (or `rad`) is
 * radians, and a bare number is degrees (`\sin(30)` is ½, the school shorthand the server
 * keeps). An angle that is none of these (`\sin(1+1)`) gives no value.
 */
import { guardReason, refuse } from "@/lib/fence/validate";
import type { LiveFunction, LiveNode } from "@/lib/math/live/read";
import {
  add,
  bitLength,
  div,
  floor,
  isInteger,
  mul,
  parseDecimal,
  powInteger,
  rational,
  rootExact,
  sub,
  toNumber,
  type Rational,
} from "@/lib/math/live/rational";

export type LiveValue = { kind: "exact"; r: Rational } | { kind: "approx"; x: number };
/** A value, or `undefined`: a calculation with no number at all (`1 ÷ 0`). */
export type LiveResult = LiveValue | { kind: "undefined" };

/** No value: the calculation is not one real number. */
const fail = (): never => refuse();

/** A float result that rounded to 0 from a number that is not 0 (`10^{-400}`): too small to hold. */
const held = (result: number, from: number): number => (result === 0 && from !== 0 ? fail() : result);

const UNDEFINED_REASON = "undefined";

/** Undefined: no number at all, real or not (`1 ÷ 0`, `tan 90°`, `log 0`). */
const undefinedValue = (): never => refuse(UNDEFINED_REASON);

const isZero = (value: LiveValue): boolean => value.kind === "exact" && value.r.n === 0n;
const ZERO: LiveValue = { kind: "exact", r: { n: 0n, d: 1n } };
/** 0 as shown, but only rounded there: no pole, and no undefined from it. */
const SMALL: LiveValue = { kind: "approx", x: 0 };

/** At an exact zero, undefined; at a decimal that rounded to 0, no value. */
const atZero = (value: LiveValue): never => (isZero(value) ? undefinedValue() : fail());

/** The largest n in n!, nCk and nPk. */
const MAX_COUNT = 170;
/** A trig value this close to 0 is shown as 0 (sin 180° is 1.2e-16 in floating point). */
const TRIG_ZERO = 1e-12;
/** A radian angle whose rounding passes this keeps fewer than the ten digits shown. */
const TRIG_DIGITS = 1e-9;
/** The rounding steps a radian angle's sine or cosine may carry. */
const TRIG_ROUNDING_STEPS = 4;

const exact = (r: Rational | null): LiveValue => ({ kind: "exact", r: r ?? fail() });

function approx(x: number): LiveValue {
  if (!Number.isFinite(x) || Math.abs(x) > 1e300) fail();
  return { kind: "approx", x };
}

export const numberOf = (value: LiveValue): number => (value.kind === "exact" ? toNumber(value.r) : value.x);

/** Both exact: the exact operation; otherwise the floating-point one. */
function combine(
  a: LiveValue,
  b: LiveValue,
  onExact: (x: Rational, y: Rational) => Rational | null,
  onApprox: (x: number, y: number) => number,
): LiveValue {
  if (a.kind === "exact" && b.kind === "exact") {
    const r = onExact(a.r, b.r);
    if (r) return exact(r);
  }
  return approx(onApprox(numberOf(a), numberOf(b)));
}

function divide(a: LiveValue, b: LiveValue): LiveValue {
  if (numberOf(b) === 0) atZero(b);
  return combine(a, b, div, (x, y) => held(x / y, x));
}

/** A whole number from an exact value, within `[min, max]`. */
function whole(value: LiveValue, min: number, max: number): bigint {
  if (value.kind !== "exact" || !isInteger(value.r)) return fail();
  if (value.r.n < BigInt(min) || value.r.n > BigInt(max)) fail();
  return value.r.n;
}

const ONE: LiveValue = { kind: "exact", r: { n: 1n, d: 1n } };

function power(base: LiveValue, exponent: LiveValue): LiveValue {
  // Anything to the power exactly 0 is exactly 1 (`e^0`, `\pi^0`; `0^0` too, as SymPy says).
  if (isZero(exponent)) return ONE;
  if (base.kind === "exact" && exponent.kind === "exact") {
    const { r: b } = base;
    const { r: e } = exponent;
    if (b.n === 0n && e.n < 0n) undefinedValue();
    if (isInteger(e)) {
      const r = bitLength(e.n) <= 32 ? powInteger(b, e.n) : null;
      if (r) return exact(r);
    } else if (bitLength(e.d) <= 16) {
      // b^(p/q): the real qth root first, then the whole power.
      if (b.n < 0n && e.d % 2n === 0n) fail();
      const root = rootExact(b, e.d);
      const r = root && powInteger(root, e.n);
      if (r) return exact(r);
      const magnitude = Math.abs(toNumber(b)) ** toNumber(e);
      return approx(b.n < 0n && e.n % 2n !== 0n ? -magnitude : magnitude);
    }
  }
  const x = numberOf(base);
  const y = numberOf(exponent);
  if (x < 0 && !Number.isInteger(y)) fail();
  if (x === 0 && y < 0) atZero(base);
  return approx(held(x ** y, x));
}

function root(radicand: LiveValue, index: bigint): LiveValue {
  if (radicand.kind === "exact") {
    if (radicand.r.n < 0n && index % 2n === 0n) fail();
    const r = rootExact(radicand.r, index);
    if (r) return exact(r);
  }
  const x = numberOf(radicand);
  if (x < 0 && index % 2n === 0n) fail();
  const magnitude = Math.abs(x) ** (1 / Number(index));
  return approx(x < 0 ? -magnitude : magnitude);
}

function factorial(n: bigint): LiveValue {
  let product = 1n;
  for (let i = 2n; i <= n; i += 1n) product *= i;
  return exact(rational(product));
}

function choose(n: bigint, k: bigint, ordered: boolean): LiveValue {
  if (k > n) fail();
  let product = 1n;
  for (let i = 0n; i < k; i += 1n) product *= n - i;
  if (ordered) return exact(rational(product));
  let kFactorial = 1n;
  for (let i = 2n; i <= k; i += 1n) kFactorial *= i;
  return exact(rational(product / kFactorial));
}

/** Within this many rounding steps of a whole number, a value floating point reached may be it. */
const WHOLE_DOUBT_STEPS = 4096;

/**
 * ⌊x⌋ or ⌈x⌉ of a floating-point value. One within its rounding of a whole number (`√2·√2` is
 * 2.0000000000000004, `(\sqrt[1000]{2})^{1000}` 2 + 2.2e-13, `1 + e^{-40}` exactly 1.0) may sit on
 * either side of it, so floating point cannot say which way it rounds: no value. `10^{10}\pi` is
 * 0.1 past a whole number, well clear of its rounding: ⌊x⌋ is 31415926535.
 */
function wholeOf(x: number, round: (x: number) => number): number {
  const whole = Math.round(x);
  const doubt = Math.abs(x - whole) <= WHOLE_DOUBT_STEPS * Number.EPSILON * Math.max(1, Math.abs(x));
  return doubt ? fail() : round(x);
}

/**
 * The float result of + or −. One that cancels to within its operands' rounding (`√2·√2 − 2`,
 * `π − 3.14159265358979`) may be 0 or a tiny number floating point cannot tell: no value. Two
 * equal floats (`π − π`) are 0, though only as a float: dividing by it still gives none. Not
 * when one was typed (`typed`): `π − 3.141592653589793` meets π's float by chance.
 */
function cancelled(result: number, x: number, y: number, typed: boolean): number {
  if (result === 0 && !typed) return 0;
  return Math.abs(result) <= CANCEL_STEPS * Number.EPSILON * Math.max(Math.abs(x), Math.abs(y)) ? fail() : result;
}

/** Rounding steps a sum of floats may carry and still be 0. */
const CANCEL_STEPS = 8;

/** `log_b(x)` exactly when `b^k = x` for a whole `k`, as `log(1000)` or `log_2(8)`. */
function exactLog(x: Rational, b: Rational): Rational | null {
  const guess = Math.round(Math.log(toNumber(x)) / Math.log(toNumber(b)));
  if (!Number.isFinite(guess) || Math.abs(guess) > 4096) return null;
  const check = powInteger(b, BigInt(guess));
  return check && check.n === x.n && check.d === x.d ? rational(BigInt(guess)) : null;
}

function logarithm(arg: LiveValue, base: LiveValue | "e"): LiveValue {
  const x = numberOf(arg);
  const b = base === "e" ? Math.E : numberOf(base);
  if (x < 0 || b <= 0) fail();
  if (x === 0) atZero(arg);
  // Base 1 exactly (`\log_{1}`); one that only rounds to 1 has a huge log, and no value here.
  const exactBase = base !== "e" && base.kind === "exact" ? base.r : null;
  if (exactBase ? exactBase.n === exactBase.d : b === 1) return exactBase ? undefinedValue() : fail();
  // The log of exactly 1 is exactly 0, in any base, so `1 ÷ ln 1` is undefined as `1 ÷ log 1` is.
  if (arg.kind === "exact" && arg.r.n === arg.r.d) return ZERO;
  if (base !== "e" && arg.kind === "exact" && base.kind === "exact") {
    const r = exactLog(arg.r, base.r);
    if (r) return exact(r);
  }
  return approx(Math.log(x) / Math.log(b));
}

const contains = (node: LiveNode, kinds: ReadonlySet<LiveNode["kind"]>): boolean => {
  if (kinds.has(node.kind)) return true;
  if (node.kind === "call") return false; // an inner call reads its own angle
  return Object.values(node).some(
    (child) => typeof child === "object" && child !== null && contains(child as LiveNode, kinds),
  );
};

const DEGREES = new Set<LiveNode["kind"]>(["degrees"]);
const RADIANS = new Set<LiveNode["kind"]>(["pi", "radians"]);

/**
 * An angle in radians, and how a zero of its sine or cosine is known. `degrees`: exact degrees
 * (`90°`, `89.99999999999999`, and an exact multiple of π, `\frac{\pi}{2}` as 90°) decide it
 * exactly. Any other (`1.5\mathrm{rad}`, `\frac{\pi}{2}+10^{-15}`) has one only at exactly 0
 * (`atZero`): the sine of any other such number is not 0, nor is its cosine.
 */
type Angle = { radians: number; degrees: Rational | null; atZero: boolean };

/** Inside an angle, what keeps it from being read with π as a number: a function (worked out
 * three times a level), or a floor or ceiling (`\lfloor 10^{10}\pi\rfloor` reads as a whole
 * number of degrees, though it is no multiple of π). */
const NOT_PI_MULTIPLE = new Set<LiveNode["kind"]>(["call", "floor", "ceil"]);

/** The angle with π read as `degrees` (180 or 360): a multiple of π becomes exact degrees. */
function withPi(node: LiveNode, degrees: string): LiveNode {
  if (node.kind === "pi") return { kind: "number", text: degrees };
  const copy: Record<string, unknown> = { ...node };
  for (const [key, value] of Object.entries(node)) {
    if (typeof value === "object" && value !== null) copy[key] = withPi(value as LiveNode, degrees);
  }
  return copy as LiveNode;
}

/**
 * An angle that is exactly `k` times π (`\frac{\pi}{2}`, `\pi-\pi`), as `180k` degrees: read
 * with π as 180 and as 360, it doubles, and the angle itself (`value`) is that many degrees. A
 * term without π (`\frac{\pi}{2}+10^{-15}`), a step that whole numbers fool (`\lfloor\pi\rfloor`
 * doubles but is 3, not π) or a function inside (worked out three times a level) leaves it `null`.
 */
function piDegrees(arg: LiveNode, value: LiveValue): Rational | null {
  if (contains(arg, NOT_PI_MULTIPLE)) return null;
  const read = (degrees: string): Rational | null => {
    const value = guardReason(() => evaluate(withPi(arg, degrees), true));
    return "value" in value && value.value.kind === "exact" ? value.value.r : null;
  };
  const half = read("180");
  const whole = read("360");
  const doubled = half && rational(2n * half.n, half.d);
  if (!half || !doubled || !whole || doubled.n !== whole.n || doubled.d !== whole.d) return null;
  const radians = (toNumber(half) * Math.PI) / 180;
  const x = numberOf(value);
  return Math.abs(x - radians) <= 1e-9 * Math.max(1, Math.abs(radians)) ? half : null;
}

/** Exact degrees as an angle, its radians from the degrees within one turn, so they stay exact. */
function inDegrees(value: LiveValue, negative: boolean): Angle {
  if (value.kind !== "exact") {
    return { radians: ((negative ? -1 : 1) * value.x * Math.PI) / 180, degrees: null, atZero: false };
  }
  const degrees = rational(negative ? -value.r.n : value.r.n, value.r.d) ?? fail();
  const turn = 360n * degrees.d;
  const within = ((degrees.n % turn) + turn) % turn;
  return { radians: (Number(within) / Number(degrees.d) * Math.PI) / 180, degrees, atZero: false };
}

/** The angle, read as the server reads it. */
function angle(arg: LiveNode): Angle {
  const signed = arg.kind === "neg" ? arg.operand : arg;
  if (contains(arg, DEGREES)) {
    // `30^{\circ}` or `-30^{\circ}`; `30^{\circ} + 15` mixes two units.
    if (signed.kind !== "degrees" || contains(arg, RADIANS)) return fail();
    // Worked out once: nested degree trig would double its cost at every level.
    return inDegrees(defined(signed.operand, true), arg.kind === "neg");
  }
  if (contains(arg, RADIANS)) {
    const value = defined(arg, true);
    const degrees = piDegrees(arg, value);
    if (degrees) return inDegrees({ kind: "exact", r: degrees }, false);
    return { radians: numberOf(value), degrees: null, atZero: isZero(value) };
  }
  if (signed.kind !== "number") return fail();
  return inDegrees(defined(arg), false);
}

/**
 * sin and cos of exact degrees, from the exact offset to the nearest quarter turn: near a pole
 * (`89.9999999999°`, 1e-10° from 90°) the small offset converts to radians with no loss, where
 * the whole angle would carry more rounding than the gap to the pole.
 */
function quarterTurns(degrees: Rational): [number, number] {
  const quarter = 90n * degrees.d;
  // The nearest quarter turn, by floor division that rounds negatives down.
  const shifted = degrees.n + quarter / 2n;
  let q = shifted / quarter;
  if (shifted % quarter !== 0n && shifted < 0n) q -= 1n;
  const offset = (Number(degrees.n - q * quarter) / Number(degrees.d) * Math.PI) / 180;
  const s = Math.sin(offset);
  const c = Math.cos(offset);
  const turn = Number(((q % 4n) + 4n) % 4n);
  return ([[s, c], [c, -s], [-s, -c], [-c, s]] as const)[turn] as [number, number];
}

/** Whether exact degrees are `offset` plus a whole number of half turns (`270°` for 90). */
const onHalfTurn = (degrees: Rational, offset: bigint): boolean =>
  (degrees.n - offset * degrees.d) % (180n * degrees.d) === 0n;

/**
 * A sine or cosine that is exactly 0 (`cos 90°`) makes tan or sec a pole, undefined, and is an
 * exact 0 (`1 ÷ sin 180°` is undefined, as csc 180° is): how that is known is the `Angle`'s.
 * One that is only small (`cos 89.99999999999999°`, `cos 1.5707963267948966 rad`) is shown as
 * 0 but is no pole: dividing by it leaves no value.
 */
function trig(fn: "sin" | "cos" | "tan" | "cot" | "sec" | "csc", { radians, degrees, atZero: zeroAngle }: Angle): LiveValue {
  const zero = (x: number) => (Math.abs(x) < TRIG_ZERO ? 0 : x);
  // A radian angle this large keeps fewer digits than the answer shows.
  if (!degrees && TRIG_ROUNDING_STEPS * Number.EPSILON * Math.abs(radians) > TRIG_DIGITS) fail();
  const [sine, cosine] = degrees ? quarterTurns(degrees) : [Math.sin(radians), Math.cos(radians)];
  const sineZero = degrees ? onHalfTurn(degrees, 0n) : zeroAngle;
  const cosineZero = degrees ? onHalfTurn(degrees, 90n) : false;
  // Exact degrees on a zero are 0 however much converting a large angle rounded (`tan 9000090°`).
  const s = sineZero ? 0 : zero(sine);
  const c = cosineZero ? 0 : zero(cosine);
  if ((fn === "tan" || fn === "sec") && c === 0) atZero(cosineZero ? ZERO : SMALL);
  if ((fn === "cot" || fn === "csc") && s === 0) atZero(sineZero ? ZERO : SMALL);
  const known = degrees && exactTrig(fn, degrees);
  if (known) return exact(known);
  const value = { sin: s, cos: c, tan: s / c, cot: c / s, sec: 1 / c, csc: 1 / s }[fn];
  const snapped = zero(value);
  if (snapped !== 0) return approx(snapped);
  const fromSine = fn === "sin" || fn === "tan";
  // Only near 0 (`sin(10^{-13}\pi)`): floating point cannot say how near, so no value.
  return (fromSine ? sineZero : cosineZero) ? ZERO : fail();
}

/** sin(30k°) for k in one turn: rational at 0°, 30°, 90°, 150°, …; `null` where it is a root. */
const HALF = { n: 1n, d: 2n };
const SINES: (Rational | null)[] = [
  { n: 0n, d: 1n }, HALF, null, { n: 1n, d: 1n }, null, HALF,
  { n: 0n, d: 1n }, { n: -1n, d: 2n }, null, { n: -1n, d: 1n }, null, { n: -1n, d: 2n },
];
/** tan(45k°) for k in one turn; `null` at the poles. */
const TANGENTS: (Rational | null)[] = [0n, 1n, null, -1n, 0n, 1n, null, -1n].map((n) =>
  n === null ? null : { n, d: 1n },
);

/** Which whole step of `step` degrees an exact angle is, within one turn, or `null`. */
function stepOf(degrees: Rational, step: bigint): number | null {
  const size = step * degrees.d;
  if (degrees.n % size !== 0n) return null;
  const steps = 360n / step;
  return Number((((degrees.n / size) % steps) + steps) % steps);
}

/**
 * A trig value that is a fraction at exact degrees (`sin 30°` is ½, `tan 45°` 1, `sec 60°` 2),
 * exactly, so `2 sin 30° − 1` is 0 and `1 ÷ (2 sin 30° − 1)` undefined, as SymPy says.
 */
function exactTrig(fn: "sin" | "cos" | "tan" | "cot" | "sec" | "csc", degrees: Rational): Rational | null {
  const k = stepOf(degrees, 30n);
  const m = stepOf(degrees, 45n);
  const sin = k === null ? null : SINES[k]!;
  const cos = k === null ? null : SINES[(k + 3) % 12]!;
  const tan = m === null ? null : TANGENTS[m]!;
  const inverse = (r: Rational | null) => (r && r.n !== 0n ? rational(r.d, r.n) : null);
  return { sin, cos, tan, cot: inverse(tan), sec: inverse(cos), csc: inverse(sin) }[fn];
}

const inRange = (x: number, ok: boolean) => (ok ? x : fail());

const ZERO_AT_ZERO = new Set<LiveFunction>(["sinh", "tanh", "asin", "atan", "asinh", "atanh"]);

function call(fn: LiveFunction, arg: LiveNode, base: LiveNode | null): LiveValue {
  if (fn === "sin" || fn === "cos" || fn === "tan" || fn === "cot" || fn === "sec" || fn === "csc") {
    return trig(fn, angle(arg));
  }
  if (contains(arg, DEGREES)) fail();
  const value = defined(arg);
  if (fn === "log") return logarithm(value, base ? defined(base) : exact(rational(10n)));
  if (fn === "ln") return arg.kind === "e" ? ONE : logarithm(value, "e");
  // Exactly 0 at exactly 0, so `1 ÷ sinh 0` is undefined as `csch 0` is.
  if (isZero(value) && ZERO_AT_ZERO.has(fn)) return ZERO;
  // exp 0 and cosh 0 are exactly 1, and so is ln e, so `\ln(e) - 1` is 0 as SymPy says.
  if (isZero(value) && (fn === "exp" || fn === "cosh")) return ONE;
  const x = numberOf(value);
  switch (fn) {
    case "exp": return approx(held(Math.exp(x), 1));
    case "asin": return approx(Math.asin(inRange(x, Math.abs(x) <= 1)));
    case "acos": return approx(Math.acos(inRange(x, Math.abs(x) <= 1)));
    case "atan": return approx(Math.atan(x));
    case "acot": return approx(x === 0 ? Math.PI / 2 : Math.atan(1 / x));
    case "asec": return approx(Math.acos(1 / inRange(x, Math.abs(x) >= 1)));
    case "acsc": return approx(Math.asin(1 / inRange(x, Math.abs(x) >= 1)));
    case "sinh": return approx(Math.sinh(x));
    case "cosh": return approx(Math.cosh(x));
    case "tanh": return approx(Math.tanh(x));
    case "coth": return approx(1 / Math.tanh(x === 0 ? atZero(value) : x));
    case "sech": return approx(held(1 / Math.cosh(x), 1));
    case "csch": return approx(held(1 / Math.sinh(x === 0 ? atZero(value) : x), 1));
    case "asinh": return approx(Math.asinh(x));
    case "acosh": return approx(Math.acosh(inRange(x, x >= 1)));
    case "atanh": return approx(Math.atanh(inRange(x, Math.abs(x) < 1)));
  }
  return fail();
}

const isPercent = (node: LiveNode): boolean =>
  node.kind === "percent" || (node.kind === "neg" && isPercent(node.operand));

/** A part whose undefined does not carry through what holds it: there it leaves no value. */
function defined(node: LiveNode, inAngle = false): LiveValue {
  const read = guardReason(() => evaluate(node, inAngle));
  return "value" in read ? read.value : fail();
}

function evaluate(node: LiveNode, inAngle = false): LiveValue {
  switch (node.kind) {
    case "number": return exact(parseDecimal(node.text));
    case "pi": return approx(Math.PI);
    case "e": return approx(Math.E);
    case "neg": {
      const v = evaluate(node.operand, inAngle);
      return v.kind === "exact" ? exact(rational(-v.r.n, v.r.d)) : approx(-v.x);
    }
    case "add": {
      // `50 + 10%` (or `50 - -10%`) is 55 on a phone calculator and 50.1 to SymPy: no answer.
      if (isPercent(node.left) || isPercent(node.right)) fail();
      const a = evaluate(node.left, inAngle);
      const b = evaluate(node.right, inAngle);
      // A float sum that cancels to its operands' rounding is a doubtful 0: no value
      // (`√2·√2 − 2`, where SymPy, exact, says 0 and its reciprocal undefined).
      const typed = a.kind === "exact" || b.kind === "exact";
      return node.op === "+"
        ? combine(a, b, add, (x, y) => cancelled(x + y, x, y, typed))
        : combine(a, b, sub, (x, y) => cancelled(x - y, x, y, typed));
    }
    case "mul": {
      const a = node.op === "mod" ? defined(node.left, inAngle) : evaluate(node.left, inAngle);
      const b = node.op === "*" ? evaluate(node.right, inAngle) : defined(node.right, inAngle);
      // Zero times any number is exactly zero (`0\pi`).
      if (node.op === "*") return isZero(a) || isZero(b) ? ZERO : combine(a, b, mul, (x, y) => (y === 0 ? 0 : held(x * y, x)));
      if (node.op === "/") return divide(a, b);
      // SymPy's Mod: the remainder takes the divisor's sign. Exact values only.
      if (b.kind === "exact" && b.r.n === 0n) return undefinedValue();
      if (a.kind !== "exact" || b.kind !== "exact") return fail();
      const q = div(a.r, b.r) ?? fail();
      return exact(sub(a.r, mul(b.r, rational(floor(q)) ?? fail()) ?? fail()));
    }
    case "frac": return divide(evaluate(node.num, inAngle), defined(node.den, inAngle));
    case "pow": return power(defined(node.base, inAngle), defined(node.exponent));
    case "root": {
      const index = node.index ? whole(defined(node.index), 2, 1000) : 2n;
      return root(defined(node.radicand, inAngle), index);
    }
    case "factorial": return factorial(whole(defined(node.operand), 0, MAX_COUNT));
    case "percent": return divide(evaluate(node.operand, inAngle), exact(rational(100n)));
    case "degrees": {
      if (!inAngle) fail();
      return approx((numberOf(evaluate(node.operand, inAngle)) * Math.PI) / 180);
    }
    case "radians": return inAngle ? evaluate(node.operand, inAngle) : fail();
    case "abs": {
      const v = defined(node.operand, inAngle);
      return v.kind === "exact" ? exact(rational(v.r.n < 0n ? -v.r.n : v.r.n, v.r.d)) : approx(Math.abs(v.x));
    }
    case "floor":
    case "ceil": {
      const v = defined(node.operand, inAngle);
      if (v.kind === "approx") return approx(wholeOf(v.x, node.kind === "floor" ? Math.floor : Math.ceil));
      const down = floor(v.r);
      return exact(rational(node.kind === "floor" || isInteger(v.r) ? down : down + 1n));
    }
    case "call": return call(node.fn, node.arg, node.base);
    // `signs.ts` picks each ± before a calculation is worked out.
    case "pm": return fail();
    case "binom":
    case "perm": {
      const n = whole(defined(node.n), 0, MAX_COUNT);
      return choose(n, whole(defined(node.k), 0, MAX_COUNT), node.kind === "perm");
    }
  }
}

const UNDEFINED: LiveResult = { kind: "undefined" };

/** The calculation's value, `undefined` when it has none, `null` when it is not one real number. */
export function evaluateCalculation(node: LiveNode): LiveResult | null {
  const read = guardReason(() => evaluate(node));
  if ("value" in read) return read.value;
  return read.refused === UNDEFINED_REASON ? UNDEFINED : null;
}
