import { converterInsertSnippet } from "@/lib/unitConverter";

export const MATH_KEYBOARD_GROUPS = ["basics", "trig", "calc", "greek", "converter"] as const;
export type MathKeyboardGroup = (typeof MATH_KEYBOARD_GROUPS)[number] | "pad";

export type MathKeyboardSymbol = {
  id: string;
  label: string;
  insert: string;
  /** Cursor offset from the start of `insert`. */
  cursorOffset: number;
  group: MathKeyboardGroup;
  /** Prose insert. Do not wrap in `$...$`. */
  plain?: boolean;
};

export type TextSelection = { start: number; end: number };

function cursorInTemplate(insert: string): number {
  const braces = insert.indexOf("{}");
  if (braces !== -1) return braces + 1;
  const parens = insert.indexOf("()");
  if (parens !== -1) return parens + 1;
  const abs = insert.indexOf("||");
  if (abs !== -1) return abs + 1;
  return insert.length;
}

function key(
  spec: Omit<MathKeyboardSymbol, "cursorOffset"> & { cursorOffset?: number },
): MathKeyboardSymbol {
  return { ...spec, cursorOffset: spec.cursorOffset ?? cursorInTemplate(spec.insert) };
}

export const MATH_KEYBOARD_SYMBOLS: readonly MathKeyboardSymbol[] = [
  key({ id: "frac", label: "□/□", insert: "\\frac{}{}", group: "basics" }),
  key({ id: "sqrt", label: "√", insert: "\\sqrt{}", group: "basics" }),
  key({ id: "nroot", label: "ⁿ√", insert: "\\sqrt[]{}", cursorOffset: 6, group: "basics" }),
  key({ id: "sup", label: "xⁿ", insert: "x^{}", group: "basics" }),
  key({ id: "sub", label: "xₙ", insert: "x_{}", group: "basics" }),
  key({ id: "abs", label: "|x|", insert: "||", group: "basics" }),
  key({ id: "pi", label: "π", insert: "\\pi ", group: "basics" }),
  key({ id: "leq", label: "≤", insert: "\\leq ", group: "basics" }),
  key({ id: "geq", label: "≥", insert: "\\geq ", group: "basics" }),
  key({ id: "neq", label: "≠", insert: "\\neq ", group: "basics" }),
  key({ id: "lt", label: "<", insert: "<", group: "basics" }),
  key({ id: "gt", label: ">", insert: ">", group: "basics" }),
  key({ id: "times", label: "×", insert: "\\times ", group: "basics" }),
  key({ id: "div", label: "÷", insert: "\\div ", group: "basics" }),
  key({ id: "minus", label: "−", insert: "-", group: "basics" }),
  key({ id: "plus", label: "+", insert: "+", group: "basics" }),
  key({ id: "eq", label: "=", insert: "=", group: "pad" }),
  key({ id: "parens", label: "( )", insert: "()", group: "pad" }),
  key({ id: "trig-theta", label: "θ", insert: "\\theta ", group: "pad" }),
  key({ id: "trig-pi", label: "π", insert: "\\pi ", group: "pad" }),

  key({ id: "sin", label: "sin", insert: "\\sin()", group: "trig" }),
  key({ id: "cos", label: "cos", insert: "\\cos()", group: "trig" }),
  key({ id: "tan", label: "tan", insert: "\\tan()", group: "trig" }),
  key({ id: "cot", label: "cot", insert: "\\cot()", group: "trig" }),
  key({ id: "sec", label: "sec", insert: "\\sec()", group: "trig" }),
  key({ id: "csc", label: "csc", insert: "\\csc()", group: "trig" }),
  key({ id: "arcsin", label: "sin⁻¹", insert: "\\arcsin()", group: "trig" }),
  key({ id: "arccos", label: "cos⁻¹", insert: "\\arccos()", group: "trig" }),
  key({ id: "arctan", label: "tan⁻¹", insert: "\\arctan()", group: "trig" }),
  key({ id: "arccot", label: "cot⁻¹", insert: "\\cot^{-1}()", group: "trig" }),
  key({ id: "arcsec", label: "sec⁻¹", insert: "\\sec^{-1}()", group: "trig" }),
  key({ id: "arccsc", label: "csc⁻¹", insert: "\\csc^{-1}()", group: "trig" }),
  key({ id: "deg", label: "°", insert: "^{\\circ}", cursorOffset: 8, group: "trig" }),
  key({ id: "rad", label: "rad", insert: "\\mathrm{rad}", group: "trig" }),
  key({ id: "sinh", label: "sinh", insert: "\\sinh()", group: "trig" }),
  key({ id: "cosh", label: "cosh", insert: "\\cosh()", group: "trig" }),
  key({ id: "tanh", label: "tanh", insert: "\\tanh()", group: "trig" }),
  key({ id: "arcsinh", label: "sinh⁻¹", insert: "\\sinh^{-1}()", group: "trig" }),
  key({ id: "arccosh", label: "cosh⁻¹", insert: "\\cosh^{-1}()", group: "trig" }),
  key({ id: "arctanh", label: "tanh⁻¹", insert: "\\tanh^{-1}()", group: "trig" }),
  key({ id: "sech", label: "sech", insert: "\\sech()", group: "pad" }),
  key({ id: "csch", label: "csch", insert: "\\csch()", group: "pad" }),
  key({ id: "coth", label: "coth", insert: "\\coth()", group: "pad" }),
  key({ id: "pi-over-6", label: "π/6", insert: "\\frac{\\pi}{6}", group: "pad" }),
  key({ id: "pi-over-4", label: "π/4", insert: "\\frac{\\pi}{4}", group: "pad" }),
  key({ id: "pi-over-3", label: "π/3", insert: "\\frac{\\pi}{3}", group: "pad" }),
  key({ id: "pi-over-2", label: "π/2", insert: "\\frac{\\pi}{2}", group: "pad" }),

  key({ id: "int", label: "∫", insert: "\\int ", group: "calc" }),
  key({ id: "dint", label: "∫□", insert: "\\int_{}^{}", group: "calc" }),
  key({ id: "iint", label: "∬", insert: "\\iint ", group: "calc" }),
  key({ id: "sum", label: "∑", insert: "\\sum_{}^{}", group: "calc" }),
  key({ id: "prod", label: "∏", insert: "\\prod_{}^{}", group: "calc" }),
  key({ id: "lim", label: "lim", insert: "\\lim_{}", group: "calc" }),
  key({ id: "infty", label: "∞", insert: "\\infty ", group: "calc" }),
  key({ id: "partial", label: "∂", insert: "\\partial ", group: "calc" }),
  key({ id: "der", label: "d/dx", insert: "\\frac{d}{dx}", group: "calc" }),
  key({ id: "der2", label: "d²/dx²", insert: "\\frac{d^{2}}{dx^{2}}", group: "calc" }),
  key({ id: "to", label: "→", insert: "\\to ", group: "calc" }),
  key({ id: "dx", label: "dx", insert: "\\,dx", group: "calc" }),
  key({ id: "log", label: "log", insert: "\\log()", group: "calc" }),
  key({ id: "ln", label: "ln", insert: "\\ln()", group: "calc" }),
  key({ id: "logn", label: "logₙ", insert: "\\log_{}()", group: "calc" }),
  key({ id: "exp", label: "exp", insert: "\\exp()", group: "calc" }),
  key({ id: "tenpow", label: "10ⁿ", insert: "10^{}", group: "calc" }),
  key({ id: "pm", label: "±", insert: "\\pm ", group: "calc" }),
  key({ id: "approx", label: "≈", insert: "\\approx ", group: "calc" }),
  key({ id: "binom", label: "nCr", insert: "\\binom{}{}", group: "calc" }),
  key({ id: "fact", label: "n!", insert: "n!", group: "calc" }),
  key({ id: "percent", label: "%", insert: "\\%", group: "calc" }),
  key({ id: "euler", label: "eⁿ", insert: "e^{}", group: "calc" }),
  key({ id: "imag", label: "i", insert: "i", group: "calc" }),
  key({ id: "oint", label: "∮", insert: "\\oint ", group: "calc" }),
  key({ id: "iiint", label: "∭", insert: "\\iiint ", group: "calc" }),
  key({ id: "nabla", label: "∇", insert: "\\nabla ", group: "calc" }),
  key({ id: "vec", label: "vec", insert: "\\vec{}", group: "calc" }),
  key({ id: "cdot", label: "·", insert: "\\cdot ", group: "calc" }),
  key({ id: "ddv", label: "d/d□", insert: "\\frac{d}{d{}}", group: "calc" }),
  key({ id: "partial-x", label: "∂/∂x", insert: "\\frac{\\partial}{\\partial x}", group: "pad" }),
  key({ id: "dy", label: "dy", insert: "\\,dy", group: "pad" }),
  key({ id: "ddt", label: "d/dt", insert: "\\frac{d}{dt}", group: "pad" }),
  key({ id: "prime", label: "f′", insert: "^{\\prime}", cursorOffset: 0, group: "pad" }),

  key({ id: "alpha", label: "α", insert: "\\alpha ", group: "greek" }),
  key({ id: "beta", label: "β", insert: "\\beta ", group: "greek" }),
  key({ id: "gamma", label: "γ", insert: "\\gamma ", group: "greek" }),
  key({ id: "delta", label: "δ", insert: "\\delta ", group: "greek" }),
  key({ id: "epsilon", label: "ε", insert: "\\varepsilon ", group: "greek" }),
  key({ id: "zeta", label: "ζ", insert: "\\zeta ", group: "greek" }),
  key({ id: "eta", label: "η", insert: "\\eta ", group: "greek" }),
  key({ id: "theta", label: "θ", insert: "\\theta ", group: "greek" }),
  key({ id: "kappa", label: "κ", insert: "\\kappa ", group: "greek" }),
  key({ id: "lambda", label: "λ", insert: "\\lambda ", group: "greek" }),
  key({ id: "mu", label: "μ", insert: "\\mu ", group: "greek" }),
  key({ id: "nu", label: "ν", insert: "\\nu ", group: "greek" }),
  key({ id: "xi", label: "ξ", insert: "\\xi ", group: "greek" }),
  key({ id: "rho", label: "ρ", insert: "\\rho ", group: "greek" }),
  key({ id: "sigma", label: "σ", insert: "\\sigma ", group: "greek" }),
  key({ id: "tau", label: "τ", insert: "\\tau ", group: "greek" }),
  key({ id: "phi", label: "φ", insert: "\\phi ", group: "greek" }),
  key({ id: "chi", label: "χ", insert: "\\chi ", group: "greek" }),
  key({ id: "psi", label: "ψ", insert: "\\psi ", group: "greek" }),
  key({ id: "omega", label: "ω", insert: "\\omega ", group: "greek" }),
  key({ id: "Gamma", label: "Γ", insert: "\\Gamma ", group: "greek" }),
  key({ id: "Delta", label: "Δ", insert: "\\Delta ", group: "greek" }),
  key({ id: "Sigma", label: "Σ", insert: "\\Sigma ", group: "greek" }),
  key({ id: "Omega", label: "Ω", insert: "\\Omega ", group: "greek" }),
  key({ id: "iota", label: "ι", insert: "\\iota ", group: "pad" }),
  key({ id: "upsilon", label: "υ", insert: "\\upsilon ", group: "pad" }),
  key({ id: "Theta", label: "Θ", insert: "\\Theta ", group: "pad" }),
  key({ id: "Phi", label: "Φ", insert: "\\Phi ", group: "pad" }),
];

/** Always-visible pad row when the math keyboard replaces QWERTY. */
export const MATH_PAD_KEYS: readonly MathKeyboardSymbol[] = [
  key({ id: "digit-1", label: "1", insert: "1", group: "pad" }),
  key({ id: "digit-2", label: "2", insert: "2", group: "pad" }),
  key({ id: "digit-3", label: "3", insert: "3", group: "pad" }),
  key({ id: "digit-4", label: "4", insert: "4", group: "pad" }),
  key({ id: "digit-5", label: "5", insert: "5", group: "pad" }),
  key({ id: "digit-6", label: "6", insert: "6", group: "pad" }),
  key({ id: "digit-7", label: "7", insert: "7", group: "pad" }),
  key({ id: "digit-8", label: "8", insert: "8", group: "pad" }),
  key({ id: "digit-9", label: "9", insert: "9", group: "pad" }),
  key({ id: "digit-0", label: "0", insert: "0", group: "pad" }),
  key({ id: "digit-dot", label: ".", insert: ".", group: "pad" }),
  key({ id: "comma", label: ",", insert: ",", group: "pad" }),
  key({ id: "var-x", label: "𝑥", insert: "x", group: "pad" }),
  key({ id: "var-y", label: "𝑦", insert: "y", group: "pad" }),
  key({ id: "var-z", label: "𝑧", insert: "z", group: "pad" }),
];

export const MATH_SYMBOL_ROW_SIZE = 6;

export function symbolsInGroup(group: MathKeyboardGroup): MathKeyboardSymbol[] {
  return MATH_KEYBOARD_SYMBOLS.filter((s) => s.group === group);
}

export function converterResultSpec(value: string, symbol: string): MathKeyboardSymbol {
  const insert = converterInsertSnippet(value, symbol);
  return key({ id: "converter-result", label: value, insert, group: "converter" });
}

/** Descriptive VoiceOver labels for math keyboard symbols (KB-005). */
export const SYMBOL_A11Y: Record<string, string> = {
  frac: "Fraction",
  sqrt: "Square root",
  nroot: "Nth root",
  sup: "Superscript",
  sub: "Subscript",
  abs: "Absolute value",
  pi: "Pi",
  leq: "Less than or equal",
  geq: "Greater than or equal",
  neq: "Not equal",
  lt: "Less than",
  gt: "Greater than",
  times: "Multiply",
  div: "Divide",
  plus: "Plus",
  minus: "Minus",
  eq: "Equals",
  parens: "Parentheses",
  "trig-theta": "Theta",
  "trig-pi": "Pi",
  sin: "Sine",
  cos: "Cosine",
  tan: "Tangent",
  cot: "Cotangent",
  sec: "Secant",
  csc: "Cosecant",
  arcsin: "Arcsine",
  arccos: "Arccosine",
  arctan: "Arctangent",
  arccot: "Arccotangent",
  arcsec: "Arcsecant",
  arccsc: "Arccosecant",
  deg: "Degree",
  rad: "Radian",
  sinh: "Hyperbolic sine",
  cosh: "Hyperbolic cosine",
  tanh: "Hyperbolic tangent",
  arcsinh: "Hyperbolic arcsine",
  arccosh: "Hyperbolic arccosine",
  arctanh: "Hyperbolic arctangent",
  sech: "Hyperbolic secant",
  csch: "Hyperbolic cosecant",
  coth: "Hyperbolic cotangent",
  "pi-over-6": "Pi over 6",
  "pi-over-4": "Pi over 4",
  "pi-over-3": "Pi over 3",
  "pi-over-2": "Pi over 2",
  int: "Integral",
  dint: "Definite integral",
  iint: "Double integral",
  sum: "Summation",
  prod: "Product",
  lim: "Limit",
  infty: "Infinity",
  partial: "Partial derivative",
  der: "Derivative",
  der2: "Second derivative",
  to: "Arrow",
  dx: "Differential",
  log: "Logarithm",
  ln: "Natural logarithm",
  logn: "Log base n",
  exp: "Exponential",
  tenpow: "Ten to the power",
  pm: "Plus minus",
  approx: "Approximately equal",
  binom: "Binomial coefficient",
  fact: "Factorial",
  percent: "Percent",
  euler: "e to the power",
  imag: "Imaginary unit i",
  oint: "Contour integral",
  iiint: "Triple integral",
  nabla: "Nabla",
  vec: "Vector",
  cdot: "Dot product",
  ddv: "Derivative with respect to",
  "partial-x": "Partial with respect to x",
  dy: "Differential dy",
  ddt: "Derivative with respect to t",
  prime: "Prime",
  alpha: "Alpha",
  beta: "Beta",
  gamma: "Gamma",
  delta: "Delta",
  epsilon: "Epsilon",
  zeta: "Zeta",
  eta: "Eta",
  theta: "Theta",
  kappa: "Kappa",
  lambda: "Lambda",
  mu: "Mu",
  nu: "Nu",
  xi: "Xi",
  rho: "Rho",
  sigma: "Sigma",
  tau: "Tau",
  phi: "Phi",
  chi: "Chi",
  psi: "Psi",
  omega: "Omega",
  Gamma: "Capital Gamma",
  Delta: "Capital Delta",
  Sigma: "Capital Sigma",
  Omega: "Capital Omega",
  iota: "Iota",
  upsilon: "Upsilon",
  Theta: "Capital Theta",
  Phi: "Capital Phi",
  "digit-dot": "Decimal point",
  comma: "Comma",
  "var-x": "Variable x",
  "var-y": "Variable y",
  "var-z": "Variable z",
  "converter-result": "Conversion result",
};

export function symbolA11yLabel(spec: MathKeyboardSymbol): string {
  return SYMBOL_A11Y[spec.id] ?? spec.label;
}

/** Symbol tabs start on their own keys. 123 opens the shared number pad. */
export function mathGroupCanToggleDigits(group: MathKeyboardGroup): boolean {
  return group === "basics" || group === "trig" || group === "calc" || group === "greek";
}

export function isCursorInsideInlineMath(text: string, pos: number): boolean {
  let dollars = 0;
  const end = Math.min(Math.max(pos, 0), text.length);
  for (let i = 0; i < end; i += 1) {
    if (text[i] === "$") dollars += 1;
  }
  return dollars % 2 === 1;
}

function lastNonSpaceChar(text: string, pos: number): string {
  let k = Math.min(Math.max(pos, 0), text.length) - 1;
  while (k >= 0 && /\s/.test(text[k]!)) k -= 1;
  return text[k] ?? "";
}

/**
 * n!: attach `!` to an existing base. Alone, leave the caret in front of `!`
 * so the next digit becomes `5!`. A `{…}` slot is painted as the characters `{}`.
 */
function factAttachInsert(text: string, start: number): { insert: string; cursorOffset: number } {
  const prev = lastNonSpaceChar(text, start);
  if (/[0-9a-zA-Z.)\]}|]/.test(prev)) {
    return { insert: "!", cursorOffset: 1 };
  }
  return { insert: "!", cursorOffset: 0 };
}

/** xⁿ / xₙ: attach the script to an existing base, otherwise insert `x`. */
function scriptAttachInsert(
  text: string,
  start: number,
  mark: "^" | "_",
): { insert: string; cursorOffset: number } {
  const prev = lastNonSpaceChar(text, start);
  if (/[0-9a-zA-Z.)\]}|]/.test(prev)) {
    return { insert: `${mark}{}`, cursorOffset: 2 };
  }
  return { insert: `x${mark}{}`, cursorOffset: 3 };
}

const DEG_CIRC = "^{\\circ}";

/**
 * °: attach after an existing base. On empty, land in front of `^{\circ}` so
 * digits prepend (`30^{\circ}`) instead of wrapping a `{30}` group the preview
 * would paint as literal braces.
 */
function degAttachInsert(text: string, start: number): { insert: string; cursorOffset: number } {
  const prev = lastNonSpaceChar(text, start);
  if (/[0-9a-zA-Z.)\]}|]/.test(prev)) {
    return { insert: DEG_CIRC, cursorOffset: DEG_CIRC.length };
  }
  return { insert: DEG_CIRC, cursorOffset: 0 };
}

function resolveInsert(
  text: string,
  start: number,
  spec: MathKeyboardSymbol,
): { insert: string; cursorOffset: number } {
  if (spec.id === "sup") return scriptAttachInsert(text, start, "^");
  if (spec.id === "sub") return scriptAttachInsert(text, start, "_");
  if (spec.id === "fact") return factAttachInsert(text, start);
  if (spec.id === "deg") return degAttachInsert(text, start);
  if (spec.id === "prime") return primeAttachInsert(text, start);
  return spec;
}

/** f′: attach `'` to an existing base. Alone, leave the caret in front of the prime. */
function primeAttachInsert(text: string, start: number): { insert: string; cursorOffset: number } {
  const prev = lastNonSpaceChar(text, start);
  if (/[0-9a-zA-Z.)\]}|]/.test(prev)) {
    return { insert: "'", cursorOffset: 1 };
  }
  return { insert: "^{\\prime}", cursorOffset: 0 };
}

function looksLikeUnitConvertDraft(text: string): boolean {
  return /\bconvert\b/i.test(text) && /\bto\b/i.test(text);
}

function fillUnitConvert(template: string, value: string): string {
  return template.replace(/^convert {2}/, `convert ${value} `);
}

function numberRangeForUnit(
  text: string,
  start: number,
): { from: number; to: number; value: string } | null {
  const dollar = text.lastIndexOf("$", Math.max(0, start - 1));
  if (dollar !== -1) {
    const close = text.indexOf("$", dollar + 1);
    if (close !== -1 && start >= dollar && start <= close + 1) {
      const inner = text.slice(dollar + 1, close).trim();
      if (/^\d+(?:\.\d+)?$/.test(inner)) {
        return { from: dollar, to: close + 1, value: inner };
      }
    }
  }
  const match = /(\d+(?:\.\d+)?)\s*$/.exec(text.slice(0, start));
  if (!match || match.index == null) return null;
  return { from: match.index, to: start, value: match[1]! };
}

export function spliceMathInsert(
  text: string,
  selection: TextSelection,
  spec: MathKeyboardSymbol,
): { text: string; selection: TextSelection } {
  const start = Math.max(0, Math.min(selection.start, text.length));
  const end = Math.max(start, Math.min(selection.end, text.length));
  if (spec.plain) {
    const num = numberRangeForUnit(text, start);
    let from = start;
    let to = end;
    let snippet: string;
    let cursorOffset: number;
    if (num) {
      from = num.from;
      to = Math.max(end, num.to);
      snippet = fillUnitConvert(spec.insert, num.value);
      cursorOffset = snippet.length;
    } else {
      snippet = spec.insert;
      cursorOffset = spec.cursorOffset;
      if (isCursorInsideInlineMath(text, start)) {
        snippet = `$${snippet}`;
        cursorOffset += 1;
      }
    }
    const next = text.slice(0, from) + snippet + text.slice(to);
    const caret = from + cursorOffset;
    return { text: next, selection: { start: caret, end: caret } };
  }
  const resolved = resolveInsert(text, start, spec);
  let snippet = resolved.insert;
  let cursorOffset = resolved.cursorOffset;
  if (!isCursorInsideInlineMath(text, start) && !looksLikeUnitConvertDraft(text)) {
    snippet = `$${resolved.insert}$`;
    cursorOffset = resolved.cursorOffset + 1;
  }
  const next = text.slice(0, start) + snippet + text.slice(end);
  const caret = start + cursorOffset;
  return { text: next, selection: { start: caret, end: caret } };
}

export function spliceBackspace(
  text: string,
  selection: TextSelection,
): { text: string; selection: TextSelection } {
  const start = Math.max(0, Math.min(selection.start, text.length));
  const end = Math.max(start, Math.min(selection.end, text.length));
  if (start !== end) {
    return { text: text.slice(0, start) + text.slice(end), selection: { start, end: start } };
  }
  if (start === 0) return { text, selection: { start, end: start } };
  return {
    text: text.slice(0, start - 1) + text.slice(end),
    selection: { start: start - 1, end: start - 1 },
  };
}
