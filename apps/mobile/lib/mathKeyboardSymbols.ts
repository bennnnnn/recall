export const MATH_KEYBOARD_GROUPS = ["basics", "trig", "calc", "greek"] as const;
export type MathKeyboardGroup = (typeof MATH_KEYBOARD_GROUPS)[number] | "pad";

export type MathKeyboardSymbol = {
  id: string;
  label: string;
  insert: string;
  /** Cursor offset from the start of `insert`. */
  cursorOffset: number;
  group: MathKeyboardGroup;
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
  key({ id: "sup", label: "xⁿ", insert: "^{}", group: "basics" }),
  key({ id: "sub", label: "xₙ", insert: "_{}", group: "basics" }),
  key({ id: "abs", label: "|x|", insert: "||", group: "basics" }),
  key({ id: "pi", label: "π", insert: "\\pi ", group: "basics" }),
  key({ id: "leq", label: "≤", insert: "\\leq ", group: "basics" }),
  key({ id: "geq", label: "≥", insert: "\\geq ", group: "basics" }),
  key({ id: "neq", label: "≠", insert: "\\neq ", group: "basics" }),
  key({ id: "times", label: "×", insert: "\\times ", group: "pad" }),
  key({ id: "div", label: "÷", insert: "\\div ", group: "pad" }),
  key({ id: "plus", label: "+", insert: "+", group: "pad" }),
  key({ id: "minus", label: "−", insert: "-", group: "pad" }),
  key({ id: "eq", label: "=", insert: "=", group: "pad" }),
  key({ id: "parens", label: "( )", insert: "()", group: "pad" }),

  key({ id: "sin", label: "sin", insert: "\\sin()", group: "trig" }),
  key({ id: "cos", label: "cos", insert: "\\cos()", group: "trig" }),
  key({ id: "tan", label: "tan", insert: "\\tan()", group: "trig" }),
  key({ id: "arcsin", label: "sin⁻¹", insert: "\\arcsin()", group: "trig" }),
  key({ id: "log", label: "log", insert: "\\log()", group: "trig" }),
  key({ id: "ln", label: "ln", insert: "\\ln()", group: "trig" }),
  key({ id: "exp", label: "exp", insert: "\\exp()", group: "trig" }),
  key({ id: "deg", label: "°", insert: "^{\\circ}", cursorOffset: 8, group: "trig" }),

  key({ id: "int", label: "∫", insert: "\\int ", group: "calc" }),
  key({ id: "dint", label: "∫□", insert: "\\int_{}^{}", group: "calc" }),
  key({ id: "sum", label: "∑", insert: "\\sum_{}^{}", group: "calc" }),
  key({ id: "prod", label: "∏", insert: "\\prod_{}^{}", group: "calc" }),
  key({ id: "lim", label: "lim", insert: "\\lim_{}", group: "calc" }),
  key({ id: "infty", label: "∞", insert: "\\infty ", group: "calc" }),
  key({ id: "partial", label: "∂", insert: "\\partial ", group: "calc" }),
  key({ id: "to", label: "→", insert: "\\to ", group: "calc" }),
  key({ id: "dx", label: "dx", insert: "\\,dx", group: "calc" }),

  key({ id: "alpha", label: "α", insert: "\\alpha ", group: "greek" }),
  key({ id: "beta", label: "β", insert: "\\beta ", group: "greek" }),
  key({ id: "gamma", label: "γ", insert: "\\gamma ", group: "greek" }),
  key({ id: "delta", label: "δ", insert: "\\delta ", group: "greek" }),
  key({ id: "theta", label: "θ", insert: "\\theta ", group: "greek" }),
  key({ id: "lambda", label: "λ", insert: "\\lambda ", group: "greek" }),
  key({ id: "mu", label: "μ", insert: "\\mu ", group: "greek" }),
  key({ id: "sigma", label: "σ", insert: "\\sigma ", group: "greek" }),
  key({ id: "phi", label: "φ", insert: "\\phi ", group: "greek" }),
  key({ id: "omega", label: "ω", insert: "\\omega ", group: "greek" }),
  key({ id: "Delta", label: "Δ", insert: "\\Delta ", group: "greek" }),
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
  key({ id: "var-x", label: "x", insert: "x", group: "pad" }),
  key({ id: "var-y", label: "y", insert: "y", group: "pad" }),
  key({ id: "var-n", label: "n", insert: "n", group: "pad" }),
];

export function symbolsInGroup(group: MathKeyboardGroup): MathKeyboardSymbol[] {
  return MATH_KEYBOARD_SYMBOLS.filter((s) => s.group === group);
}

export function isCursorInsideInlineMath(text: string, pos: number): boolean {
  let dollars = 0;
  const end = Math.min(Math.max(pos, 0), text.length);
  for (let i = 0; i < end; i += 1) {
    if (text[i] === "$") dollars += 1;
  }
  return dollars % 2 === 1;
}

export function spliceMathInsert(
  text: string,
  selection: TextSelection,
  spec: MathKeyboardSymbol,
): { text: string; selection: TextSelection } {
  const start = Math.max(0, Math.min(selection.start, text.length));
  const end = Math.max(start, Math.min(selection.end, text.length));
  let snippet = spec.insert;
  let cursorOffset = spec.cursorOffset;
  if (!isCursorInsideInlineMath(text, start)) {
    snippet = `$${spec.insert}$`;
    cursorOffset = spec.cursorOffset + 1;
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

export type LatexGroup = { open: number; close: number };

export function readBraceGroup(text: string, from: number): LatexGroup | null {
  let i = from;
  while (i < text.length && text[i] === " ") i += 1;
  if (text[i] !== "{") return null;
  const open = i;
  let depth = 0;
  for (; i < text.length; i += 1) {
    if (text[i] === "{") depth += 1;
    else if (text[i] === "}") {
      depth -= 1;
      if (depth === 0) return { open, close: i };
    }
  }
  return null;
}

export function findFracSlots(text: string): { num: LatexGroup; den: LatexGroup }[] {
  const out: { num: LatexGroup; den: LatexGroup }[] = [];
  let i = 0;
  while (i < text.length) {
    const idx = text.indexOf("\\frac", i);
    if (idx === -1) break;
    const num = readBraceGroup(text, idx + 5);
    if (!num) {
      i = idx + 5;
      continue;
    }
    const den = readBraceGroup(text, num.close + 1);
    if (!den) {
      i = num.close + 1;
      continue;
    }
    out.push({ num, den });
    i = den.close + 1;
  }
  return out;
}

/** True when the caret is inside `{…}` (including sitting on the closing `}`). */
export function caretInGroup(caret: number, group: LatexGroup): boolean {
  return caret > group.open && caret <= group.close;
}

export function readDelimGroup(
  text: string,
  openIdx: number,
  openCh: string,
  closeCh: string,
): LatexGroup | null {
  if (text[openIdx] !== openCh) return null;
  let depth = 0;
  for (let i = openIdx; i < text.length; i += 1) {
    if (text[i] === openCh) depth += 1;
    else if (text[i] === closeCh) {
      depth -= 1;
      if (depth === 0) return { open: openIdx, close: i };
    }
  }
  return null;
}

/** Left-to-right editable `{…}` / `(…)` / `[…]` / `|…|` groups, including nested. */
export function findEditSlots(text: string): LatexGroup[] {
  const out: LatexGroup[] = [];
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const prev = text[i - 1];
    if (prev === "\\") continue;
    if (ch === "{" || ch === "(" || ch === "[") {
      const closeCh = ch === "{" ? "}" : ch === "(" ? ")" : "]";
      const group = readDelimGroup(text, i, ch, closeCh);
      if (group) out.push(group);
    } else if (ch === "|") {
      const close = text.indexOf("|", i + 1);
      if (close !== -1) {
        out.push({ open: i, close });
        i = close;
      }
    }
  }
  return out;
}

export function innermostSlot(text: string, caret: number): LatexGroup | null {
  const containing = findEditSlots(text).filter((s) => caretInGroup(caret, s));
  if (containing.length === 0) return null;
  return containing.reduce((best, slot) =>
    slot.close - slot.open < best.close - best.open ? slot : best,
  );
}

/** After the last box of a construct, move past it — do not wrap back to the first box. */
export function nextEditSlotCaret(text: string, caret: number): number | null {
  const slots = findEditSlots(text);
  if (slots.length === 0) return null;
  const current = innermostSlot(text, caret);
  if (!current) {
    const firstAfter = slots.find((s) => s.open >= caret);
    return firstAfter ? firstAfter.close : null;
  }
  const later = slots.filter((s) => s.open > current.close);
  if (later.length === 0) return current.close + 1;
  const nextOpen = Math.min(...later.map((s) => s.open));
  return later.find((s) => s.open === nextOpen)!.close;
}

const STAY_IN_SLOT = /^(digit-|var-)/;

/**
 * Operators and new templates after a filled last box continue the expression
 * (`8/8 × 2`) instead of nesting inside that box.
 */
export function caretForInsert(text: string, caret: number, spec: MathKeyboardSymbol): number {
  if (STAY_IN_SLOT.test(spec.id)) return caret;
  const current = innermostSlot(text, caret);
  if (!current) return caret;
  if (current.close - current.open <= 1) return caret;
  if (caret !== current.close) return caret;
  const later = findEditSlots(text).some((s) => s.open > current.close);
  if (later) return caret;
  return current.close + 1;
}

/** Second tap on fraction: jump num → empty den instead of inserting another \\frac. */
export function fracTapAdvancesToDen(text: string, caret: number): number | null {
  for (const frac of findFracSlots(text)) {
    const numFilled = frac.num.close - frac.num.open > 1;
    const denEmpty = frac.den.close - frac.den.open === 1;
    if (numFilled && denEmpty && caretInGroup(caret, frac.num)) return frac.den.close;
  }
  return null;
}

/** After filling an empty frac numerator with a non-digit atom, land in the den. */
export function autoAdvanceFracDen(
  before: string,
  beforeCaret: number,
  after: string,
  afterCaret: number,
  spec: MathKeyboardSymbol,
): number | null {
  if (STAY_IN_SLOT.test(spec.id)) return null;
  const beforeFrac = findFracSlots(before).find((f) => caretInGroup(beforeCaret, f.num));
  if (!beforeFrac) return null;
  if (beforeFrac.num.close - beforeFrac.num.open !== 1) return null;
  const afterFrac = findFracSlots(after).find((f) => caretInGroup(afterCaret, f.num));
  if (!afterFrac) return null;
  if (afterFrac.num.close - afterFrac.num.open <= 1) return null;
  if (afterFrac.den.close - afterFrac.den.open !== 1) return null;
  return afterFrac.den.close;
}

export type PadCell =
  | { kind: "insert"; spec: MathKeyboardSymbol }
  | { kind: "backspace" }
  | { kind: "next" };

function padSpec(id: string): MathKeyboardSymbol {
  const spec = MATH_PAD_KEYS.find((s) => s.id === id) ?? MATH_KEYBOARD_SYMBOLS.find((s) => s.id === id);
  if (!spec) throw new Error(`missing pad spec ${id}`);
  return spec;
}

/** 5-column calculator grid under the function tabs. */
export const MATH_NUMPAD_ROWS: PadCell[][] = [
  [
    { kind: "insert", spec: padSpec("digit-7") },
    { kind: "insert", spec: padSpec("digit-8") },
    { kind: "insert", spec: padSpec("digit-9") },
    { kind: "insert", spec: padSpec("times") },
    { kind: "backspace" },
  ],
  [
    { kind: "insert", spec: padSpec("digit-4") },
    { kind: "insert", spec: padSpec("digit-5") },
    { kind: "insert", spec: padSpec("digit-6") },
    { kind: "insert", spec: padSpec("div") },
    { kind: "next" },
  ],
  [
    { kind: "insert", spec: padSpec("digit-1") },
    { kind: "insert", spec: padSpec("digit-2") },
    { kind: "insert", spec: padSpec("digit-3") },
    { kind: "insert", spec: padSpec("minus") },
    { kind: "insert", spec: padSpec("parens") },
  ],
  [
    { kind: "insert", spec: padSpec("digit-0") },
    { kind: "insert", spec: padSpec("digit-dot") },
    { kind: "insert", spec: padSpec("var-x") },
    { kind: "insert", spec: padSpec("plus") },
    { kind: "insert", spec: padSpec("eq") },
  ],
];
