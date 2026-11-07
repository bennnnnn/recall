import { joinsCommandName } from "@/lib/math/commandName";
import {
  findDraftNodes,
  nodeSlots,
  shiftDraftNodes,
  templateAround,
  type DraftNode,
  type DraftTemplate,
} from "@/lib/math/draftNodes";
import { caretInGroup, type LatexGroup, type TextSelection } from "@/lib/math/keyboardSymbols";

/** Caret just after an opening `$` so the next insert/delete is at the front. */
export function caretBeforeExpression(text: string): number {
  return text.startsWith("$") ? 1 : 0;
}

/** Caret just inside a trailing `$…$` pair so the next insert stays in math. */
export function caretAfterExpression(text: string): number {
  if (text.endsWith("$") && text.includes("$")) return Math.max(0, text.length - 1);
  return text.length;
}

/** `\mathrm{rad}` and `\binom{}{}` are one key. Nested braces stay out of this. */
const COMMAND_GROUPS = /\\[A-Za-z]+(?:\{[^{}]*\})+$/;
const COMMAND_GROUPS_START = /^\\[A-Za-z]+(?:\{[^{}]*\})+/;
const SYMBOL_COMMAND = /\\[^A-Za-z\s]$/;
const SYMBOL_COMMAND_START = /^\\[^A-Za-z\s]/;

function lastTokenLength(prefix: string): number {
  const wrapped = prefix.match(COMMAND_GROUPS);
  if (wrapped) return wrapped[0].length;
  const symbol = prefix.match(SYMBOL_COMMAND);
  if (symbol) return symbol[0].length;
  const cmd = prefix.match(/\\[A-Za-z]+[ ]?$/);
  if (cmd) return cmd[0].length;
  return prefix.length > 0 ? 1 : 0;
}

function firstTokenLength(s: string): number {
  const wrapped = s.match(COMMAND_GROUPS_START);
  if (wrapped) return wrapped[0].length;
  const symbol = s.match(SYMBOL_COMMAND_START);
  if (symbol) return symbol[0].length;
  const cmd = s.match(/^\\[A-Za-z]+[ ]?/);
  if (cmd) return cmd[0].length;
  return s.length > 0 ? 1 : 0;
}

function matchingCloserOpen(text: string, closeIdx: number, min: number): number | null {
  const closeCh = text[closeIdx];
  const openCh = closeCh === "}" ? "{" : closeCh === "]" ? "[" : closeCh === ")" ? "(" : "";
  if (!openCh) return null;
  let depth = 0;
  for (let i = closeIdx; i >= min; i -= 1) {
    if (text[i] === closeCh) depth += 1;
    else if (text[i] === openCh) {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return null;
}

function plainCommandTouching(text: string, cut: number, min: number): [number, number] | null {
  const re = /\\[A-Za-z]+(?:\{[^{}]*\})+/g;
  const slice = text.slice(min);
  let match: RegExpExecArray | null;
  while ((match = re.exec(slice))) {
    const from = min + match.index;
    const to = from + match[0].length;
    if (cut > from && cut <= to) return [from, to];
  }
  return null;
}

function deleteRange(
  text: string,
  from: number,
  to: number,
): { text: string; selection: TextSelection } {
  return collapseEmptyMath(text.slice(0, from) + text.slice(to), from);
}

function deleteTokenBefore(
  text: string,
  cut: number,
  min: number,
): { text: string; selection: TextSelection } | null {
  if (cut <= min) return null;
  // A template inside the box peels as it does on its own: `\frac{1}{2}` loses the 2 first.
  const template = templateAround(text, cut, min);
  if (template) return templateBackspace(text, template, cut);
  const command = plainCommandTouching(text, cut, min);
  if (command) return deleteRange(text, command[0], command[1]);
  const prev = text[cut - 1];
  if (prev === "{" && (text[cut] === "}" || text[cut] === "]" || text[cut] === ")")) {
    let from = cut - 1;
    if (from > min && (text[from - 1] === "^" || text[from - 1] === "_") && text[from - 2] !== "\\") {
      from -= 1;
    }
    if (from < min) return null;
    return deleteRange(text, from, cut + 1);
  }
  if (prev === "}" || prev === "]" || prev === ")") {
    const inside = text.slice(min, cut);
    // A finished `\mathrm{rad}` / `\text{cm}` / `\binom{}{}` deletes as one key.
    if (!COMMAND_GROUPS.test(inside)) {
      const open = matchingCloserOpen(text, cut - 1, min);
      if (open != null && open >= min) {
        if (open + 1 === cut - 1) {
          let from = open;
          if (
            from > min &&
            (text[from - 1] === "^" || text[from - 1] === "_") &&
            text[from - 2] !== "\\"
          ) {
            from -= 1;
          }
          const next = text.slice(0, from) + text.slice(cut);
          return collapseEmptyMath(next, from);
        }
        return deleteTokenBefore(text, cut - 1, open + 1);
      }
    }
  }
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
  // A template the box starts with keeps both halves: `\lfloor x \rfloor` loses the x.
  const template = templateAround(text, from + 1, from);
  if (template) return templateForward(text, template);
  const n = firstTokenLength(text.slice(from, max));
  if (n === 0 || from + n > max) return null;
  const next = text.slice(0, from) + text.slice(from + n);
  return collapseEmptyMath(next, from);
}

/**
 * Backspace at `pos` in a template: the token before the caret in its box (or the
 * box's first token), else the last token of an earlier box; an empty template goes whole.
 */
function templateBackspace(
  text: string,
  node: DraftTemplate,
  pos: number,
): { text: string; selection: TextSelection } {
  const slots = nodeSlots(node);
  const inner = slots.filter(
    (s) => caretInGroup(pos, s) || (text[pos] === "$" && caretInGroup(pos - 1, s)),
  );
  const slot =
    (inner.length > 0
      ? inner.reduce((best, s) => (s.close - s.open < best.close - best.open ? s : best))
      : slots.filter((s) => s.close < pos).at(-1)) ?? slots[slots.length - 1]!;

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
  return deleteRange(text, node.start, node.end);
}

/** Delete forward into a template: its first box's first token, or the template once that box is empty. */
function templateForward(text: string, node: DraftTemplate): { text: string; selection: TextSelection } {
  const first = nodeSlots(node)[0]!;
  const forward = first.close - first.open > 1 ? deleteTokenAfter(text, first.open + 1, first.close) : null;
  return forward ?? deleteRange(text, node.start, node.end);
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

/** Stops among `nodes`: each token of their text, each side of a template and every box inside it. */
function addNodeStops(text: string, nodes: DraftNode[], stops: Set<number>): void {
  for (const node of nodes) {
    if (node.kind === "text") {
      addTokenStops(text, node.start, node.end, stops);
      continue;
    }
    stops.add(node.start);
    stops.add(node.end);
    for (const slot of nodeSlots(node)) {
      stops.add(slot.open + 1);
      const inner = findDraftNodes(text.slice(slot.open + 1, slot.close));
      addNodeStops(text, shiftDraftNodes(inner, slot.open + 1), stops);
      stops.add(slot.close);
    }
  }
}

/** Places you can park the caret by tapping or pressing ← →, in boxes at any depth. */
function mathCaretStops(text: string): number[] {
  const stops = new Set<number>();
  stops.add(caretBeforeExpression(text));
  stops.add(caretAfterExpression(text));
  addNodeStops(text, findDraftNodes(text), stops);
  return [...stops].filter((p) => p >= 0 && p <= text.length).sort((a, b) => a - b);
}

function collapseEmptyMath(
  text: string,
  caret: number,
): { text: string; selection: TextSelection } {
  // Only strip $ delimiters when the math span is truly empty (no content between pairs).
  // Don't globally remove $$ — it would corrupt $$display math$$ with content.
  const stripped = text.replace(/\$\$/g, "");
  const hasNonMathContent = stripped.trim().length > 0;
  let next = hasNonMathContent ? text : stripped;
  if (next === "$") next = "";
  let pos = Math.max(0, Math.min(caret, next.length));
  // A deletion never joins a letter to a command's name: `\rceil2y` loses its 2 as `\rceil y`.
  if (joinsCommandName(next.slice(0, pos), next.slice(pos))) {
    next = `${next.slice(0, pos)} ${next.slice(pos)}`;
    pos += 1;
  }
  return commitBackspace({ text: next, selection: { start: pos, end: pos } });
}

function snapCaretOffRaw(text: string, pos: number): number {
  if (!text) return 0;
  const p = Math.max(0, Math.min(pos, text.length));
  const rawAt = (i: number) => {
    const c = text[i];
    return c === "\\" || c === "{" || c === "}";
  };
  const onRaw = p < text.length && rawAt(p);
  const afterRaw = p > 0 && rawAt(p - 1) && text[p] !== "$";
  if (!onRaw && !afterRaw) return p;
  const stops = mathCaretStops(text);
  // A caret on a stop is in a box already: the one the edit happened in.
  if (stops.includes(p)) return p;
  const prev = [...stops].reverse().find((s) => (onRaw ? s <= p : s < p));
  return prev ?? p;
}

function commitBackspace(result: { text: string; selection: TextSelection }): {
  text: string;
  selection: TextSelection;
} {
  const start = snapCaretOffRaw(result.text, result.selection.start);
  return { text: result.text, selection: { start, end: start } };
}

function slotCut(text: string, slot: LatexGroup, caret: number): number {
  if (caret < text.length && text[caret] === "$") return slot.close;
  return Math.min(Math.max(caret, slot.open + 1), slot.close);
}

/**
 * Backspace that keeps templates valid: delete digits/commands, not `{` / `}`.
 * Empty boxes peel back into the previous box; an empty template is removed. A
 * template inside a box, a `\lfloor … \rfloor` or a `(…)` included, peels the same way.
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
  const structures = findDraftNodes(text).filter((n): n is DraftTemplate => n.kind !== "text");
  const node = structures.find((n) => pos > n.start && pos <= n.end);
  if (node) return templateBackspace(text, node, pos);

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
    if (first) return templateForward(text, first);
    const innerStart = caretBeforeExpression(text);
    const innerEnd = caretAfterExpression(text);
    const forward = deleteTokenAfter(text, Math.min(innerStart, innerEnd), innerEnd);
    if (forward) return forward;
    return collapseEmptyMath("", 0);
  }
  return commitBackspace(
    deleteTokenBefore(text, cut, 0) ?? { text, selection: { start: pos, end: pos } },
  );
}
