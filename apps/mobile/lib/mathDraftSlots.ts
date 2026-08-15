import {
  caretInGroup,
  readBraceGroup,
  readDelimGroup,
  type LatexGroup,
  type TextSelection,
} from "@/lib/mathKeyboardSymbols";

export type DraftNode =
  | { kind: "text"; start: number; end: number }
  | { kind: "frac"; start: number; end: number; num: LatexGroup; den: LatexGroup }
  | { kind: "sqrt"; start: number; end: number; index?: LatexGroup; body: LatexGroup }
  | { kind: "script"; start: number; end: number; mark: "^" | "_"; body: LatexGroup }
  | { kind: "abs"; start: number; end: number; body: LatexGroup }
  | { kind: "group"; start: number; end: number; open: string; close: string; body: LatexGroup };

function cmdAt(text: string, i: number, cmd: string): boolean {
  if (!text.startsWith(cmd, i)) return false;
  const next = text[i + cmd.length];
  return !next || !/[A-Za-z]/.test(next);
}

function tryFrac(text: string, i: number): Extract<DraftNode, { kind: "frac" }> | null {
  if (!cmdAt(text, i, "\\frac")) return null;
  const num = readBraceGroup(text, i + 5);
  if (!num) return null;
  const den = readBraceGroup(text, num.close + 1);
  if (!den) return null;
  return { kind: "frac", start: i, end: den.close + 1, num, den };
}

function trySqrt(text: string, i: number): Extract<DraftNode, { kind: "sqrt" }> | null {
  if (!cmdAt(text, i, "\\sqrt")) return null;
  let j = i + 5;
  let index: LatexGroup | undefined;
  if (text[j] === "[") {
    const g = readDelimGroup(text, j, "[", "]");
    if (!g) return null;
    index = g;
    j = g.close + 1;
  }
  const body = readBraceGroup(text, j);
  if (!body) return null;
  return { kind: "sqrt", start: i, end: body.close + 1, index, body };
}

function tryScript(text: string, i: number): Extract<DraftNode, { kind: "script" }> | null {
  const mark = text[i];
  if (mark !== "^" && mark !== "_") return null;
  if (text[i - 1] === "\\") return null;
  const body = readBraceGroup(text, i + 1);
  if (!body) return null;
  return { kind: "script", start: i, end: body.close + 1, mark, body };
}

function tryAbs(text: string, i: number): Extract<DraftNode, { kind: "abs" }> | null {
  if (text[i] !== "|" || text[i - 1] === "\\") return null;
  const close = text.indexOf("|", i + 1);
  if (close === -1) return null;
  return { kind: "abs", start: i, end: close + 1, body: { open: i, close } };
}

function tryGroup(text: string, i: number): Extract<DraftNode, { kind: "group" }> | null {
  if (text[i] !== "(" || text[i - 1] === "\\") return null;
  const body = readDelimGroup(text, i, "(", ")");
  if (!body) return null;
  let start = i;
  if (i > 0 && /[A-Za-z]/.test(text[i - 1]!)) {
    let j = i - 1;
    while (j >= 0 && /[A-Za-z]/.test(text[j]!)) j -= 1;
    if (text[j] === "\\") start = j;
  }
  return { kind: "group", start, end: body.close + 1, open: "(", close: ")", body };
}

/** Top-level tappable constructs in the composer draft (source offsets). */
export function findDraftNodes(text: string): DraftNode[] {
  const nodes: DraftNode[] = [];
  let i = 0;
  let textStart = 0;
  const flush = (end: number) => {
    if (end > textStart) nodes.push({ kind: "text", start: textStart, end });
  };
  while (i < text.length) {
    const frac = tryFrac(text, i);
    if (frac) {
      flush(i);
      nodes.push(frac);
      textStart = i = frac.end;
      continue;
    }
    const sqrt = trySqrt(text, i);
    if (sqrt) {
      flush(i);
      nodes.push(sqrt);
      textStart = i = sqrt.end;
      continue;
    }
    const script = tryScript(text, i);
    if (script) {
      flush(i);
      nodes.push(script);
      textStart = i = script.end;
      continue;
    }
    const abs = tryAbs(text, i);
    if (abs) {
      flush(i);
      nodes.push(abs);
      textStart = i = abs.end;
      continue;
    }
    const group = tryGroup(text, i);
    if (group) {
      flush(i);
      nodes.push(group);
      textStart = i = group.end;
      continue;
    }
    i += 1;
  }
  flush(text.length);
  return nodes;
}

export function hasTappableDraftSlot(nodes: DraftNode[]): boolean {
  return nodes.some((n) => n.kind !== "text");
}

/** Caret just after an opening `$` so the next insert/delete is at the front. */
export function caretBeforeExpression(text: string): number {
  return text.startsWith("$") ? 1 : 0;
}

/** Caret just inside a trailing `$…$` pair so the next insert stays in math. */
export function caretAfterExpression(text: string): number {
  if (text.endsWith("$") && text.includes("$")) return Math.max(0, text.length - 1);
  return text.length;
}

function nodeSlots(node: Exclude<DraftNode, { kind: "text" }>): LatexGroup[] {
  if (node.kind === "frac") return [node.num, node.den];
  if (node.kind === "sqrt") return node.index ? [node.index, node.body] : [node.body];
  return [node.body];
}

function lastTokenLength(prefix: string): number {
  const cmd = prefix.match(/\\[A-Za-z]+[ ]?$/);
  if (cmd) return cmd[0].length;
  return prefix.length > 0 ? 1 : 0;
}

function firstTokenLength(s: string): number {
  const cmd = s.match(/^\\[A-Za-z]+[ ]?/);
  if (cmd) return cmd[0].length;
  return s.length > 0 ? 1 : 0;
}

function deleteTokenBefore(
  text: string,
  cut: number,
  min: number,
): { text: string; selection: TextSelection } | null {
  if (cut <= min) return null;
  const n = lastTokenLength(text.slice(min, cut));
  if (n === 0 || cut - n < min) return null;
  const delAt = cut - n;
  const next = text.slice(0, delAt) + text.slice(cut);
  return collapseEmptyMath(next, delAt);
}

function deleteTokenAfter(
  text: string,
  from: number,
  max: number,
): { text: string; selection: TextSelection } | null {
  if (from >= max) return null;
  const n = firstTokenLength(text.slice(from, max));
  if (n === 0 || from + n > max) return null;
  const next = text.slice(0, from) + text.slice(from + n);
  return collapseEmptyMath(next, from);
}

function addTokenStops(text: string, from: number, to: number, stops: Set<number>): void {
  let i = from;
  while (i < to) {
    if (text[i] !== "$") stops.add(i);
    const n = firstTokenLength(text.slice(i, to).replace(/^\$/, "")) || 1;
    if (text[i] === "$") {
      i += 1;
      continue;
    }
    i += n;
  }
}

/** Places you can park the caret by tapping or pressing ← →. */
export function mathCaretStops(text: string): number[] {
  const stops = new Set<number>();
  stops.add(caretBeforeExpression(text));
  stops.add(caretAfterExpression(text));
  for (const node of findDraftNodes(text)) {
    if (node.kind === "text") {
      addTokenStops(text, node.start, node.end, stops);
      continue;
    }
    for (const slot of nodeSlots(node)) {
      stops.add(slot.open + 1);
      addTokenStops(text, slot.open + 1, slot.close, stops);
      stops.add(slot.close);
    }
  }
  return [...stops].filter((p) => p >= 0 && p <= text.length).sort((a, b) => a - b);
}

export function stepMathCaret(text: string, caret: number, dir: -1 | 1): number {
  const stops = mathCaretStops(text);
  if (stops.length === 0) return caret;
  if (dir > 0) return stops.find((s) => s > caret) ?? stops[stops.length - 1]!;
  return [...stops].reverse().find((s) => s < caret) ?? stops[0]!;
}

function collapseEmptyMath(
  text: string,
  caret: number,
): { text: string; selection: TextSelection } {
  let next = text.replace(/\$\$/g, "");
  if (next === "$") next = "";
  const pos = Math.max(0, Math.min(caret, next.length));
  return { text: next, selection: { start: pos, end: pos } };
}

function slotCut(text: string, slot: LatexGroup, caret: number): number {
  if (caret < text.length && text[caret] === "$") return slot.close;
  return Math.min(Math.max(caret, slot.open + 1), slot.close);
}

/**
 * Backspace that keeps templates valid: delete digits/commands, not `{` / `}`.
 * Empty boxes peel back into the previous box; an empty template is removed.
 */
export function spliceMathBackspace(
  text: string,
  selection: TextSelection,
): { text: string; selection: TextSelection } {
  const start = Math.max(0, Math.min(selection.start, text.length));
  const end = Math.max(start, Math.min(selection.end, text.length));
  if (start !== end) {
    return collapseEmptyMath(text.slice(0, start) + text.slice(end), start);
  }
  if (start === 0) return { text, selection: { start, end: start } };

  const pos =
    start === text.length && text.endsWith("$") ? start - 1 : start;
  const structures = findDraftNodes(text).filter(
    (n): n is Exclude<DraftNode, { kind: "text" }> => n.kind !== "text",
  );
  const node = structures.find((n) => pos > n.start && pos <= n.end);

  if (node) {
    const slots = nodeSlots(node);
    const inner = slots.filter(
      (s) => caretInGroup(pos, s) || (text[pos] === "$" && caretInGroup(pos - 1, s)),
    );
    const slot =
      (inner.length > 0
        ? inner.reduce((best, s) => (s.close - s.open < best.close - best.open ? s : best))
        : slots.filter((s) => s.close < pos).at(-1)) ?? slots.at(-1);
    if (!slot) return deleteTokenBefore(text, pos, 0) ?? { text, selection: { start: pos, end: pos } };

    if (slot.close - slot.open > 1) {
      const cut = slotCut(text, slot, pos);
      const deleted = deleteTokenBefore(text, cut, slot.open + 1);
      if (deleted) return deleted;
      const forward = deleteTokenAfter(text, slot.open + 1, slot.close);
      if (forward) return forward;
    }

    for (let i = slots.indexOf(slot) - 1; i >= 0; i -= 1) {
      const prev = slots[i]!;
      if (prev.close - prev.open > 1) {
        const deleted = deleteTokenBefore(text, prev.close, prev.open + 1);
        if (deleted) return deleted;
      }
    }

    const next = text.slice(0, node.start) + text.slice(node.end);
    return collapseEmptyMath(next, node.start);
  }

  let cut = pos;
  if (text[cut] === "$") {
    /* delete the token before the closing $, never the dollar itself */
  } else if (cut === text.length && text[cut - 1] === "$") {
    cut -= 1;
  }
  const prefix = text.slice(0, cut);
  const n = lastTokenLength(prefix);
  const piece = n > 0 ? prefix.slice(-n) : "";
  if (/^[{}()[\]|]$/.test(piece)) {
    const ended = structures.filter((s) => s.end <= cut).at(-1);
    if (ended) {
      const last = nodeSlots(ended).at(-1);
      if (last && last.close - last.open > 1) {
        const deleted = deleteTokenBefore(text, last.close, last.open + 1);
        if (deleted) return deleted;
      }
      return collapseEmptyMath(text.slice(0, ended.start) + text.slice(ended.end), ended.start);
    }
  }
  if (piece === "$" || pos <= caretBeforeExpression(text)) {
    const first = structures.find((n) => n.start >= pos) ?? structures[0];
    if (first) {
      const slot = nodeSlots(first)[0];
      if (slot && slot.close - slot.open > 1) {
        const forward = deleteTokenAfter(text, slot.open + 1, slot.close);
        if (forward) return forward;
      }
      return collapseEmptyMath(text.slice(0, first.start) + text.slice(first.end), first.start);
    }
    const innerStart = caretBeforeExpression(text);
    const innerEnd = caretAfterExpression(text);
    const forward = deleteTokenAfter(text, Math.min(innerStart, innerEnd), innerEnd);
    if (forward) return forward;
    return collapseEmptyMath("", 0);
  }
  return deleteTokenBefore(text, cut, 0) ?? { text, selection: { start: pos, end: pos } };
}
