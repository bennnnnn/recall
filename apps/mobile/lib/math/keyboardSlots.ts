import type { MathKeyboardSymbol } from "@/lib/math/keyboardCatalog";

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

/** Delimiters written as commands, with the glyphs a draft draws for them. */
const COMMAND_PAIRS = [
  { open: "\\{", close: "\\}", glyphs: ["{", "}"] },
  { open: "\\lfloor", close: "\\rfloor", glyphs: ["⌊", "⌋"] },
  { open: "\\lceil", close: "\\rceil", glyphs: ["⌈", "⌉"] },
] as const;

type CommandPair = LatexGroup & { end: number; glyphs: readonly [string, string] };

/** `cmd` at `i`, and not the front of a longer command name (`\lfloor`, not `\lfloors`). */
function commandAt(text: string, i: number, cmd: string): boolean {
  if (!text.startsWith(cmd, i)) return false;
  return !/[A-Za-z]$/.test(cmd) || !/[A-Za-z]/.test(text[i + cmd.length] ?? "");
}

/** After a word command, the space that ends its name (`\lfloor x`, not `\lfloorx`). */
function nameSpace(text: string, at: number, cmd: string): number {
  return text[at] === " " && /[A-Za-z]$/.test(cmd) ? 1 : 0;
}

/**
 * `\{ … \}`, `\lfloor … \rfloor`, `\lceil … \rceil`. `open` is the opener's last
 * character (the space a word command takes), `close` is the `\` of the closer, so
 * the box between them is the same shape as `{…}` and `|…|`. `end` is past the closer
 * and the space that keeps a letter after it out of its name (`\rfloor y`), so a
 * backspace never takes that space without its pair.
 */
export function readCommandPair(text: string, from: number): CommandPair | null {
  const pair = COMMAND_PAIRS.find((p) => commandAt(text, from, p.open));
  if (!pair) return null;
  let j = from + pair.open.length;
  j += nameSpace(text, j, pair.open);
  const open = j - 1;
  let depth = 1;
  while (j < text.length) {
    if (commandAt(text, j, pair.open)) {
      depth += 1;
      j += pair.open.length;
      continue;
    }
    if (commandAt(text, j, pair.close)) {
      depth -= 1;
      const end = j + pair.close.length;
      if (depth === 0) return { open, close: j, end: end + nameSpace(text, end, pair.close), glyphs: pair.glyphs };
      j = end;
      continue;
    }
    j += 1;
  }
  return null;
}

/** Left-to-right editable `{…}` / `(…)` / `[…]` / command-pair / `|…|` groups, including nested. */
function findEditSlots(text: string): LatexGroup[] {
  const out: LatexGroup[] = [];
  for (let i = 0; i < text.length; i += 1) {
    const pair = readCommandPair(text, i);
    if (pair) out.push({ open: pair.open, close: pair.close });
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

const STAY_IN_SLOT = /^(digit-|var-)/;

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

/** `\int_{a}^{b}`, `\sum_{…}^{…}`, `\prod_{…}^{…}`: lower bound, then upper bound. */
function boundPairs(command: string) {
  return (text: string): SlotPair[] => {
    const out: SlotPair[] = [];
    let i = 0;
    while (i < text.length) {
      const idx = text.indexOf(`${command}_`, i);
      if (idx === -1) break;
      const lower = readBraceGroup(text, idx + command.length + 1);
      if (!lower || text[lower.close + 1] !== "^") {
        i = idx + command.length;
        continue;
      }
      const upper = readBraceGroup(text, lower.close + 2);
      if (!upper) {
        i = lower.close + 1;
        continue;
      }
      out.push({ first: lower, second: upper });
      i = upper.close + 1;
    }
    return out;
  };
}

function bracePairs(command: string) {
  return (text: string): SlotPair[] => {
    const out: SlotPair[] = [];
    let i = 0;
    while (i < text.length) {
      const idx = text.indexOf(command, i);
      if (idx === -1) break;
      const first = readBraceGroup(text, idx + command.length);
      const second = first ? readBraceGroup(text, first.close + 1) : null;
      if (first && second) out.push({ first, second });
      i = (second ?? first)?.close ?? idx + command.length;
      i += 1;
    }
    return out;
  };
}

const TAP_PAIRS: Record<string, (text: string) => SlotPair[]> = {
  frac: fracPairs,
  nroot: nrootPairs,
  logn: lognPairs,
  dint: boundPairs("\\int"),
  sum: boundPairs("\\sum"),
  prod: boundPairs("\\prod"),
  binom: bracePairs("\\binom"),
};

function pairsForTap(specId: string): ((text: string) => SlotPair[]) | null {
  return TAP_PAIRS[specId] ?? null;
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

/** Second tap on a two-box key (□/□, ⁿ√, logₙ, ∫□, ∑, ∏, nCr): first box → empty second box. */
export function tapAdvancesToNextSlot(text: string, caret: number, specId: string): number | null {
  const find = pairsForTap(specId);
  if (!find) return null;
  return tapAdvancesPair(text, caret, find);
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
