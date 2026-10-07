import {
  MATH_KEYBOARD_SYMBOLS,
  MATH_PAD_KEYS,
  MATH_SYMBOL_ROW_SIZE,
  symbolsInGroup,
  type MathKeyboardGroup,
  type MathKeyboardSymbol,
} from "@/lib/math/keyboardCatalog";

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

/** Previous box — inverse of nextEditSlotCaret; does not wrap. */
export function prevEditSlotCaret(text: string, caret: number): number | null {
  const slots = findEditSlots(text);
  if (slots.length === 0) return null;
  const current = innermostSlot(text, caret);
  if (!current) {
    const earlier = slots.filter((s) => s.close < caret);
    if (earlier.length === 0) return null;
    return earlier.reduce((best, s) => (s.open > best.open ? s : best)).close;
  }
  const earlier = slots.filter((s) => s.close < current.open);
  if (earlier.length === 0) return current.open + 1;
  return earlier.reduce((best, s) => (s.open > best.open ? s : best)).close;
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

type SlotPair = { first: LatexGroup; second: LatexGroup };

function slotEmpty(group: LatexGroup): boolean {
  return group.close - group.open === 1;
}

function slotFilled(group: LatexGroup): boolean {
  return group.close - group.open > 1;
}

export function findNrootSlots(text: string): { index: LatexGroup; radicand: LatexGroup }[] {
  const out: { index: LatexGroup; radicand: LatexGroup }[] = [];
  let i = 0;
  while (i < text.length) {
    const idx = text.indexOf("\\sqrt[", i);
    if (idx === -1) break;
    const index = readDelimGroup(text, idx + 5, "[", "]");
    if (!index) {
      i = idx + 5;
      continue;
    }
    const radicand = readBraceGroup(text, index.close + 1);
    if (!radicand) {
      i = index.close + 1;
      continue;
    }
    out.push({ index, radicand });
    i = radicand.close + 1;
  }
  return out;
}

export function findLognSlots(text: string): { base: LatexGroup; arg: LatexGroup }[] {
  const out: { base: LatexGroup; arg: LatexGroup }[] = [];
  let i = 0;
  while (i < text.length) {
    const idx = text.indexOf("\\log_", i);
    if (idx === -1) break;
    const base = readBraceGroup(text, idx + 5);
    if (!base) {
      i = idx + 5;
      continue;
    }
    let j = base.close + 1;
    while (j < text.length && text[j] === " ") j += 1;
    const arg = readDelimGroup(text, j, "(", ")");
    if (!arg) {
      i = base.close + 1;
      continue;
    }
    out.push({ base, arg });
    i = arg.close + 1;
  }
  return out;
}

function fracPairs(text: string): SlotPair[] {
  return findFracSlots(text).map((f) => ({ first: f.num, second: f.den }));
}

function nrootPairs(text: string): SlotPair[] {
  return findNrootSlots(text).map((f) => ({ first: f.index, second: f.radicand }));
}

function lognPairs(text: string): SlotPair[] {
  return findLognSlots(text).map((f) => ({ first: f.base, second: f.arg }));
}

function pairsForTap(specId: string): ((text: string) => SlotPair[]) | null {
  if (specId === "frac") return fracPairs;
  if (specId === "nroot") return nrootPairs;
  if (specId === "logn") return lognPairs;
  return null;
}

function tapAdvancesPair(
  text: string,
  caret: number,
  findPairs: (text: string) => SlotPair[],
): number | null {
  for (const pair of findPairs(text)) {
    if (slotFilled(pair.first) && slotEmpty(pair.second) && caretInGroup(caret, pair.first)) {
      return pair.second.close;
    }
  }
  return null;
}

/** Second tap on frac / ⁿ√ / logₙ: jump the filled first box → empty second box. */
export function tapAdvancesToNextSlot(text: string, caret: number, specId: string): number | null {
  const find = pairsForTap(specId);
  if (!find) return null;
  return tapAdvancesPair(text, caret, find);
}

/** Second tap on fraction: jump num → empty den instead of inserting another \\frac. */
export function fracTapAdvancesToDen(text: string, caret: number): number | null {
  return tapAdvancesToNextSlot(text, caret, "frac");
}

function autoAdvancePair(
  before: string,
  beforeCaret: number,
  after: string,
  afterCaret: number,
  findPairs: (text: string) => SlotPair[],
): number | null {
  const beforePair = findPairs(before).find((p) => caretInGroup(beforeCaret, p.first));
  if (!beforePair || !slotEmpty(beforePair.first)) return null;
  const afterPair = findPairs(after).find((p) => caretInGroup(afterCaret, p.first));
  if (!afterPair || !slotFilled(afterPair.first) || !slotEmpty(afterPair.second)) return null;
  return afterPair.second.close;
}

/** After filling an empty first box with a non-digit atom, land in the empty second box. */
export function autoAdvanceNextEmptySlot(
  before: string,
  beforeCaret: number,
  after: string,
  afterCaret: number,
  spec: MathKeyboardSymbol,
): number | null {
  if (STAY_IN_SLOT.test(spec.id)) return null;
  return (
    autoAdvancePair(before, beforeCaret, after, afterCaret, fracPairs) ??
    autoAdvancePair(before, beforeCaret, after, afterCaret, nrootPairs) ??
    autoAdvancePair(before, beforeCaret, after, afterCaret, lognPairs)
  );
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
  return autoAdvancePair(before, beforeCaret, after, afterCaret, fracPairs);
}

export type PadCell =
  | { kind: "insert"; spec: MathKeyboardSymbol }
  | { kind: "backspace" }
  | { kind: "digits" }
  | { kind: "spacer" };

function padSpec(id: string): MathKeyboardSymbol {
  const spec = MATH_PAD_KEYS.find((s) => s.id === id) ?? MATH_KEYBOARD_SYMBOLS.find((s) => s.id === id);
  if (!spec) throw new Error(`missing pad spec ${id}`);
  return spec;
}

function insertRow(ids: readonly string[]): PadCell[] {
  return ids.map((id) => ({ kind: "insert" as const, spec: padSpec(id) }));
}

/** Basics is 6×4. The fourth row starts with the 123 link; x y z = () . are the row above it. */
function basicsRows(): PadCell[][] {
  return [
    insertRow(["frac", "sqrt", "nroot", "sup", "sub", "abs"]),
    insertRow(["pi", "leq", "geq", "neq", "lt", "gt"]),
    insertRow(["var-x", "var-y", "var-z", "eq", "parens", "digit-dot"]),
    [
      { kind: "digits" },
      ...insertRow(["times", "div", "minus", "plus"]),
      { kind: "backspace" },
    ],
  ];
}

/** Fills the short Trig row with keys that are not already on Basics. */
const TRIG_ROW_TAIL = ["trig-theta", "sech", "csch", "coth"] as const;

/** Symbol rows for a tab, always 6-wide. Digits live on the 123 pad, not in these rows. */
export function symbolRowsForGroup(group: MathKeyboardGroup): PadCell[][] {
  if (group === "basics") return basicsRows();
  const functions = symbolsInGroup(group);
  const rows: PadCell[][] = [];
  for (let i = 0; i < functions.length; i += MATH_SYMBOL_ROW_SIZE) {
    rows.push(functions.slice(i, i + MATH_SYMBOL_ROW_SIZE).map((spec) => ({ kind: "insert" as const, spec })));
  }
  if (rows.length === 0) return rows;
  const last = rows[rows.length - 1]!;
  while (last.length < MATH_SYMBOL_ROW_SIZE) last.push({ kind: "spacer" });
  if (group === "trig") {
    let extra = 0;
    for (let i = 0; i < last.length && extra < TRIG_ROW_TAIL.length; i++) {
      if (last[i]?.kind === "spacer") {
        last[i] = { kind: "insert", spec: padSpec(TRIG_ROW_TAIL[extra]!) };
        extra++;
      }
    }
  }
  return rows;
}

/** Digit grid. x, y, z, =, (), and the dot live on the Basics row above 123. */
export const MATH_NUMPAD_ROWS: PadCell[][] = [
  insertRow(["digit-7", "digit-8", "digit-9", "digit-4", "digit-5", "digit-6"]),
  insertRow(["digit-1", "digit-2", "digit-3", "digit-0", "digit-dot", "comma"]),
];

