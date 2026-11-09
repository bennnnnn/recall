/**
 * Works out a calculation `read.ts` read, for the composer's live answer.
 *
 * A value stays an exact fraction while every step allows it (+ − × ÷, whole powers, perfect
 * roots, %, !, |x|, mod, logs that come out whole); π, e, trig, other logs and other roots
 * give a decimal. Anything the server would not call one real number gives no value: a zero
 * divisor, a root of a negative, a log of zero, tan 90°, `50 + 10%` (55 or 50.1).
 *
 * Angles follow the server's reading: `30^{\circ}` is degrees, an angle with π (or `rad`) is
 * radians, and a bare number is degrees (`\sin(30)` is ½, the school shorthand the server
 * keeps). An angle that is none of these (`\sin(1+1)`) gives no value.
 */
import { guard, refuse } from "@/lib/fence/validate";
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

/** No value: the calculation is not one real number. */
const fail = (): never => refuse();

/** The largest n in n!, nCk and nPk. */
const MAX_COUNT = 170;
/** A trig value this close to 0 is 0 (sin 180° is 1.2e-16 in floating point). */
const TRIG_ZERO = 1e-12;

const exact = (r: Rational | null): LiveValue => ({ kind: "exact", r: r ?? fail() });

function approx(x: number): LiveValue {
  if (!Number.isFinite(x) || Math.abs(x) > 1e300) fail();
  return { kind: "approx", x };
}

const num = (value: LiveValue): number => (value.kind === "exact" ? toNumber(value.r) : value.x);

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
  return approx(onApprox(num(a), num(b)));
}

function divide(a: LiveValue, b: LiveValue): LiveValue {
  if (num(b) === 0 || (b.kind === "exact" && b.r.n === 0n)) fail();
  return combine(a, b, div, (x, y) => x / y);
}

/** A whole number from an exact value, within `[min, max]`. */
function whole(value: LiveValue, min: number, max: number): bigint {
  if (value.kind !== "exact" || !isInteger(value.r)) return fail();
  if (value.r.n < BigInt(min) || value.r.n > BigInt(max)) fail();
  return value.r.n;
}

function power(base: LiveValue, exponent: LiveValue): LiveValue {
  if (base.kind === "exact" && exponent.kind === "exact") {
    const { r: b } = base;
    const { r: e } = exponent;
    if (b.n === 0n && e.n < 0n) fail();
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
  const x = num(base);
  const y = num(exponent);
  if (x < 0 && !Number.isInteger(y)) fail();
  if (x === 0 && y < 0) fail();
  return approx(x ** y);
}

function root(radicand: LiveValue, index: bigint): LiveValue {
  if (radicand.kind === "exact") {
    if (radicand.r.n < 0n && index % 2n === 0n) fail();
    const r = rootExact(radicand.r, index);
    if (r) return exact(r);
  }
  const x = num(radicand);
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

/** A floating-point value within a hair of a whole number is that number (for ⌊x⌋, ⌈x⌉). */
function nearWhole(x: number): number {
  const rounded = Math.round(x);
  return Math.abs(x - rounded) <= 1e-9 * Math.max(1, Math.abs(x)) ? rounded : x;
}

/** `log_b(x)` exactly when `b^k = x` for a whole `k`, as `log(1000)` or `log_2(8)`. */
function exactLog(x: Rational, b: Rational): Rational | null {
  const guess = Math.round(Math.log(toNumber(x)) / Math.log(toNumber(b)));
  if (!Number.isFinite(guess) || Math.abs(guess) > 4096) return null;
  const check = powInteger(b, BigInt(guess));
  return check && check.n === x.n && check.d === x.d ? rational(BigInt(guess)) : null;
}

function logarithm(arg: LiveValue, base: LiveValue | "e"): LiveValue {
  const x = num(arg);
  const b = base === "e" ? Math.E : num(base);
  if (x <= 0 || b <= 0 || b === 1) fail();
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

/** The angle in radians, read as the server reads it. */
function angle(arg: LiveNode): number {
  const signed = arg.kind === "neg" ? arg.operand : arg;
  if (contains(arg, DEGREES)) {
    // `30^{\circ}` or `-30^{\circ}`; `30^{\circ} + 15` mixes two units.
    if (signed.kind !== "degrees" || contains(arg, RADIANS)) return fail();
    return num(evaluate(arg, true));
  }
  if (contains(arg, RADIANS)) return num(evaluate(arg, true));
  if (signed.kind !== "number") return fail();
  return (num(evaluate(arg)) * Math.PI) / 180;
}

function trig(fn: "sin" | "cos" | "tan" | "cot" | "sec" | "csc", radians: number): LiveValue {
  const zero = (x: number) => (Math.abs(x) < TRIG_ZERO ? 0 : x);
  const s = zero(Math.sin(radians));
  const c = zero(Math.cos(radians));
  if ((fn === "tan" || fn === "sec") && c === 0) fail();
  if ((fn === "cot" || fn === "csc") && s === 0) fail();
  const value = { sin: s, cos: c, tan: s / c, cot: c / s, sec: 1 / c, csc: 1 / s }[fn];
  return approx(zero(value));
}

const inRange = (x: number, ok: boolean) => (ok ? x : fail());

function call(fn: LiveFunction, arg: LiveNode, base: LiveNode | null): LiveValue {
  if (fn === "sin" || fn === "cos" || fn === "tan" || fn === "cot" || fn === "sec" || fn === "csc") {
    return trig(fn, angle(arg));
  }
  if (contains(arg, DEGREES)) fail();
  const value = evaluate(arg);
  if (fn === "log") return logarithm(value, base ? evaluate(base) : exact(rational(10n)));
  if (fn === "ln") return logarithm(value, "e");
  const x = num(value);
  switch (fn) {
    case "exp": return approx(Math.exp(x));
    case "asin": return approx(Math.asin(inRange(x, Math.abs(x) <= 1)));
    case "acos": return approx(Math.acos(inRange(x, Math.abs(x) <= 1)));
    case "atan": return approx(Math.atan(x));
    case "acot": return approx(x === 0 ? Math.PI / 2 : Math.atan(1 / x));
    case "asec": return approx(Math.acos(1 / inRange(x, Math.abs(x) >= 1)));
    case "acsc": return approx(Math.asin(1 / inRange(x, Math.abs(x) >= 1)));
    case "sinh": return approx(Math.sinh(x));
    case "cosh": return approx(Math.cosh(x));
    case "tanh": return approx(Math.tanh(x));
    case "coth": return approx(1 / Math.tanh(inRange(x, x !== 0)));
    case "sech": return approx(1 / Math.cosh(x));
    case "csch": return approx(1 / Math.sinh(inRange(x, x !== 0)));
    case "asinh": return approx(Math.asinh(x));
    case "acosh": return approx(Math.acosh(inRange(x, x >= 1)));
    case "atanh": return approx(Math.atanh(inRange(x, Math.abs(x) < 1)));
  }
  return fail();
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
      // `50 + 10%` is 55 on a phone calculator and 50.1 to SymPy: no answer.
      if (node.left.kind === "percent" || node.right.kind === "percent") fail();
      const a = evaluate(node.left, inAngle);
      const b = evaluate(node.right, inAngle);
      return node.op === "+" ? combine(a, b, add, (x, y) => x + y) : combine(a, b, sub, (x, y) => x - y);
    }
    case "mul": {
      const a = evaluate(node.left, inAngle);
      const b = evaluate(node.right, inAngle);
      if (node.op === "*") return combine(a, b, mul, (x, y) => x * y);
      if (node.op === "/") return divide(a, b);
      // SymPy's Mod: the remainder takes the divisor's sign. Exact values only.
      if (a.kind !== "exact" || b.kind !== "exact" || b.r.n === 0n) return fail();
      const q = div(a.r, b.r) ?? fail();
      return exact(sub(a.r, mul(b.r, rational(floor(q)) ?? fail()) ?? fail()));
    }
    case "frac": return divide(evaluate(node.num, inAngle), evaluate(node.den, inAngle));
    case "pow": return power(evaluate(node.base, inAngle), evaluate(node.exponent));
    case "root": {
      const index = node.index ? whole(evaluate(node.index), 2, 1000) : 2n;
      return root(evaluate(node.radicand, inAngle), index);
    }
    case "factorial": return factorial(whole(evaluate(node.operand), 0, MAX_COUNT));
    case "percent": return divide(evaluate(node.operand, inAngle), exact(rational(100n)));
    case "degrees": {
      if (!inAngle) fail();
      return approx((num(evaluate(node.operand, inAngle)) * Math.PI) / 180);
    }
    case "radians": return inAngle ? evaluate(node.operand, inAngle) : fail();
    case "abs": {
      const v = evaluate(node.operand, inAngle);
      return v.kind === "exact" ? exact(rational(v.r.n < 0n ? -v.r.n : v.r.n, v.r.d)) : approx(Math.abs(v.x));
    }
    case "floor":
    case "ceil": {
      const v = evaluate(node.operand, inAngle);
      if (v.kind === "approx") {
        const x = nearWhole(v.x);
        return approx(node.kind === "floor" ? Math.floor(x) : Math.ceil(x));
      }
      const down = floor(v.r);
      return exact(rational(node.kind === "floor" || isInteger(v.r) ? down : down + 1n));
    }
    case "call": return call(node.fn, node.arg, node.base);
    case "binom":
    case "perm": {
      const n = whole(evaluate(node.n), 0, MAX_COUNT);
      return choose(n, whole(evaluate(node.k), 0, MAX_COUNT), node.kind === "perm");
    }
  }
}

/** The calculation's value, or `null` when it is not one real number. */
export function evaluateCalculation(node: LiveNode): LiveValue | null {
  return guard(() => evaluate(node));
}
