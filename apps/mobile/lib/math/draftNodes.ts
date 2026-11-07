/**
 * The composer draft read as templates: where each fraction, root, script and bracket
 * pair sits in the source, and the boxes it holds. The draft's preview draws these, and
 * its editor (`draftSlots.ts`) deletes through them.
 */
import {
  caretInGroup,
  readBraceGroup,
  readCommandPair,
  readDelimGroup,
  type LatexGroup,
} from "@/lib/math/keyboardSymbols";

export type DraftNode =
  | { kind: "text"; start: number; end: number }
  | { kind: "frac"; start: number; end: number; num: LatexGroup; den: LatexGroup }
  | { kind: "sqrt"; start: number; end: number; index?: LatexGroup; body: LatexGroup }
  | { kind: "script"; start: number; end: number; mark: "^" | "_"; body: LatexGroup }
  | { kind: "binom"; start: number; end: number; n: LatexGroup; k: LatexGroup }
  | { kind: "vec"; start: number; end: number; body: LatexGroup }
  | { kind: "abs"; start: number; end: number; body: LatexGroup }
  | { kind: "brace"; start: number; end: number; body: LatexGroup }
  /** `open` and `close` are what the draft draws on each side of the box (`sin(`, `⌊`, `]`). */
  | { kind: "group"; start: number; end: number; open: string; close: string; body: LatexGroup };

/** A node with boxes: everything but plain text. */
export type DraftTemplate = Exclude<DraftNode, { kind: "text" }>;

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

function tryBinom(text: string, i: number): Extract<DraftNode, { kind: "binom" }> | null {
  if (!cmdAt(text, i, "\\binom")) return null;
  const n = readBraceGroup(text, i + 6);
  if (!n) return null;
  const k = readBraceGroup(text, n.close + 1);
  if (!k) return null;
  return { kind: "binom", start: i, end: k.close + 1, n, k };
}

function tryVec(text: string, i: number): Extract<DraftNode, { kind: "vec" }> | null {
  if (!cmdAt(text, i, "\\vec")) return null;
  const body = readBraceGroup(text, i + 4);
  if (!body) return null;
  return { kind: "vec", start: i, end: body.close + 1, body };
}

function tryScript(text: string, i: number): Extract<DraftNode, { kind: "script" }> | null {
  const mark = text[i];
  if (mark !== "^" && mark !== "_") return null;
  if (text[i - 1] === "\\") return null;
  const body = readBraceGroup(text, i + 1);
  if (!body) return null;
  return { kind: "script", start: i, end: body.close + 1, mark, body };
}

/** `{` that closes a `\command` stays with that command (`\mathrm{rad}`). */
function braceFollowsCommand(text: string, braceIndex: number): boolean {
  let j = braceIndex - 1;
  while (j >= 0 && /[A-Za-z]/.test(text[j]!)) j -= 1;
  return text[j] === "\\";
}

function tryBrace(text: string, i: number): Extract<DraftNode, { kind: "brace" }> | null {
  if (text[i] !== "{") return null;
  const prev = text[i - 1];
  if (prev === "\\" || prev === "^" || prev === "_" || prev === "}") return null;
  if (braceFollowsCommand(text, i)) return null;
  const body = readBraceGroup(text, i);
  if (!body) return null;
  return { kind: "brace", start: i, end: body.close + 1, body };
}

function tryAbs(text: string, i: number): Extract<DraftNode, { kind: "abs" }> | null {
  if (text[i] !== "|" || text[i - 1] === "\\") return null;
  const close = text.indexOf("|", i + 1);
  if (close === -1) return null;
  return { kind: "abs", start: i, end: close + 1, body: { open: i, close } };
}

function tryCommandPair(text: string, i: number): Extract<DraftNode, { kind: "group" }> | null {
  const pair = readCommandPair(text, i);
  if (!pair) return null;
  const [open, close] = pair.glyphs;
  return { kind: "group", start: i, end: pair.end, open, close, body: { open: pair.open, close: pair.close } };
}

function tryGroup(text: string, i: number): Extract<DraftNode, { kind: "group" }> | null {
  const openCh = text[i];
  if ((openCh !== "(" && openCh !== "[") || text[i - 1] === "\\") return null;
  const closeCh = openCh === "(" ? ")" : "]";
  const body = readDelimGroup(text, i, openCh, closeCh);
  if (!body) return null;
  let start = i;
  if (openCh === "(" && i > 0 && /[A-Za-z]/.test(text[i - 1]!)) {
    let j = i - 1;
    while (j >= 0 && /[A-Za-z]/.test(text[j]!)) j -= 1;
    if (text[j] === "\\") start = j;
  }
  const open = `${text.slice(start + 1, i)}${openCh}`;
  return { kind: "group", start, end: body.close + 1, open, close: closeCh, body };
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
    const binom = tryBinom(text, i);
    if (binom) {
      flush(i);
      nodes.push(binom);
      textStart = i = binom.end;
      continue;
    }
    const vec = tryVec(text, i);
    if (vec) {
      flush(i);
      nodes.push(vec);
      textStart = i = vec.end;
      continue;
    }
    const pair = tryCommandPair(text, i);
    if (pair) {
      flush(i);
      nodes.push(pair);
      textStart = i = pair.end;
      continue;
    }
    const brace = tryBrace(text, i);
    if (brace) {
      flush(i);
      nodes.push(brace);
      textStart = i = brace.end;
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
    if (group && group.start >= textStart) {
      flush(group.start);
      nodes.push(group);
      textStart = i = group.end;
      continue;
    }
    i += 1;
  }
  flush(text.length);
  return nodes;
}

function shiftGroup(group: LatexGroup, delta: number): LatexGroup {
  return { open: group.open + delta, close: group.close + delta };
}

/** Rebase nodes parsed from a slot's inner text onto the full draft. */
export function shiftDraftNodes(nodes: DraftNode[], delta: number): DraftNode[] {
  if (delta === 0) return nodes;
  return nodes.map((node) => {
    const start = node.start + delta;
    const end = node.end + delta;
    switch (node.kind) {
      case "text":
        return { kind: "text", start, end };
      case "frac":
        return {
          kind: "frac",
          start,
          end,
          num: shiftGroup(node.num, delta),
          den: shiftGroup(node.den, delta),
        };
      case "sqrt":
        return {
          kind: "sqrt",
          start,
          end,
          index: node.index ? shiftGroup(node.index, delta) : undefined,
          body: shiftGroup(node.body, delta),
        };
      case "script":
        return { kind: "script", start, end, mark: node.mark, body: shiftGroup(node.body, delta) };
      case "binom":
        return { kind: "binom", start, end, n: shiftGroup(node.n, delta), k: shiftGroup(node.k, delta) };
      case "group":
        return { ...node, start, end, body: shiftGroup(node.body, delta) };
      case "vec":
      case "abs":
      case "brace":
        return { ...node, start, end, body: shiftGroup(node.body, delta) };
    }
  });
}

export function nodeSlots(node: DraftTemplate): LatexGroup[] {
  if (node.kind === "frac") return [node.num, node.den];
  if (node.kind === "binom") return [node.n, node.k];
  if (node.kind === "sqrt") return node.index ? [node.index, node.body] : [node.body];
  return [node.body];
}

/**
 * The template around `cut` that starts in the box beginning at `min`: the outermost
 * one inside that box, reached through the templates that hold the box itself. A box's
 * own `\frac{1}{2}` or `\lfloor x \rfloor` is then edited box by box, as it is at the top.
 */
export function templateAround(
  text: string,
  cut: number,
  min: number,
  nodes: DraftNode[] = findDraftNodes(text),
): DraftTemplate | undefined {
  const node = nodes.find((n): n is DraftTemplate => n.kind !== "text" && cut > n.start && cut <= n.end);
  if (!node || node.start >= min) return node;
  const slot = nodeSlots(node).find((s) => caretInGroup(cut, s));
  if (!slot) return undefined;
  const inner = shiftDraftNodes(findDraftNodes(text.slice(slot.open + 1, slot.close)), slot.open + 1);
  return templateAround(text, cut, min, inner);
}
