import { readGroup } from "@/lib/math/latexGroups";
import { preprocessLatex } from "@/lib/math/latexPreprocess";
import {
  MAX_MATH_NEST_DEPTH,
  NATIVE_LITERAL_APOSTROPHE_MARKER,
  NATIVE_LITERAL_LEFT_BRACE_MARKER,
  NATIVE_LITERAL_RIGHT_BRACE_MARKER,
  NATIVE_UPRIGHT_END_MARKER,
  NATIVE_UPRIGHT_START_MARKER,
  TEXT_STYLE_COMMANDS,
} from "@/lib/math/textMarkers";
import type { MathAccentKind, MathSegment } from "@/lib/math/textTypes";

// Copy and read-aloud still spell an accent as a combining mark. The screen
// draws a measured rule from the accent segment; these marks are not painted.
const ACCENT_MARK: Record<MathAccentKind, string> = {
  overline: "̅",
  underline: "̲",
  hat: "̂",
  tilde: "̃",
  vec: "⃗",
  vecLeft: "⃖",
  bar: "̄",
  ddot: "̈",
  dot: "̇",
};

const ACCENT_SPAN = new Set([
  "\\overrightarrow",
  "\\overleftarrow",
  "\\widehat",
  "\\widetilde",
]);

const ACCENT_OPENERS: { cmd: string; kind: MathAccentKind }[] = [
  { cmd: "\\overrightarrow", kind: "vec" },
  { cmd: "\\overleftarrow", kind: "vecLeft" },
  { cmd: "\\overline", kind: "overline" },
  { cmd: "\\underline", kind: "underline" },
  { cmd: "\\widehat", kind: "hat" },
  { cmd: "\\widetilde", kind: "tilde" },
  { cmd: "\\ddot", kind: "ddot" },
  { cmd: "\\hat", kind: "hat" },
  { cmd: "\\vec", kind: "vec" },
  { cmd: "\\bar", kind: "bar" },
  { cmd: "\\dot", kind: "dot" },
  { cmd: "\\tilde", kind: "tilde" },
];

/** Combining mark applied per-character so copy spells the whole accented
 * run. The screen draws one measured rule; these marks are not painted. */
function markEachChar(text: string, mark: string): string {
  return Array.from(text)
    .map((ch) => (ch === " " ? ch : `${ch}${mark}`))
    .join("");
}

/** Braced scripts and root indexes that are only ordinary letters stay
 * strings. Upright runs keep their segment so the renderer preserves their
 * font style inside a subscript (for example, `t_{\mathrm{flight}}`). */
function plainScriptPieces(segments: MathSegment[]): string | null {
  let plain = "";
  for (const segment of segments) {
    if (segment.type !== "text") return null;
    plain += segment.value;
  }
  return plain;
}

function parseFrac(
  input: string,
  start: number,
  depth: number,
): { seg: MathSegment; next: number } | null {
  if (!input.startsWith("\\frac", start)) return null;
  let i = start + 5;
  while (input[i] === " ") i += 1;
  const numGroup = readGroup(input, i);
  if (!numGroup) return null;
  i = numGroup.next;
  while (input[i] === " ") i += 1;
  const denGroup = readGroup(input, i);
  if (!denGroup) return null;
  return {
    seg: {
      type: "frac",
      // Keep num/den as parsed segments (not flattened strings) so the
      // renderer can render superscripts/subscripts/fractions INSIDE a
      // fraction — \frac{x^2}{4} shows x² in the numerator, not literal "x^2".
      num: parseSimpleLatex(numGroup.value, depth + 1),
      den: parseSimpleLatex(denGroup.value, depth + 1),
    },
    next: denGroup.next,
  };
}

/**
 * \sqrt{x} / \sqrt[n]{x} — mirrors parseFrac: readGroup tracks brace depth,
 * so a radicand containing its own braces (\sqrt{\frac{M}{2}}) parses
 * correctly instead of a flat `[^}]+` regex stopping at the FIRST `}`.
 */
function parseSqrt(
  input: string,
  start: number,
  depth: number,
): { seg: MathSegment; next: number } | null {
  if (!input.startsWith("\\sqrt", start)) return null;
  let i = start + 5;
  let degree: string | undefined;
  let index: MathSegment[] | undefined;
  if (input[i] === "[") {
    const close = input.indexOf("]", i);
    if (close === -1) return null;
    const raw = input.slice(i + 1, close);
    const parsed = parseSimpleLatex(raw, depth + 1);
    const plain = plainScriptPieces(parsed);
    if (plain == null) index = parsed;
    else degree = plain;
    i = close + 1;
  }
  while (input[i] === " ") i += 1;
  const group = readGroup(input, i);
  if (group) {
    return {
      seg: { type: "sqrt", body: parseSimpleLatex(group.value, depth + 1), degree, index },
      next: group.next,
    };
  }
  // `\sqrt\text{x}` / `\sqrt\frac{1}{2}` — the radicand is one atom, not the
  // letters "sqrt" followed by that atom.
  const atom = readLeadingAtom(input, i, depth);
  if (atom) {
    return { seg: { type: "sqrt", body: atom.body, degree, index }, next: atom.next };
  }
  // \sqrt without braces (\sqrt4, \sqrt 4) — bare single-token radicand.
  const bare = input.slice(i).match(/^[0-9a-zA-Z]+/)?.[0];
  if (bare) {
    return { seg: { type: "sqrt", body: [{ type: "text", value: bare }], degree, index }, next: i + bare.length };
  }
  return null;
}

/**
 * \\cancel{3} / \\bcancel / \\xcancel — strike a cancelled factor in a divide step.
 */
function parseCancel(
  input: string,
  start: number,
  depth: number,
): { seg: MathSegment; next: number } | null {
  const names = ["\\xcancel", "\\bcancel", "\\cancel"] as const;
  const name = names.find((n) => input.startsWith(n, start));
  if (!name) return null;
  let i = start + name.length;
  while (input[i] === " ") i += 1;
  const group = readGroup(input, i);
  if (group) {
    return {
      seg: { type: "cancel", body: parseSimpleLatex(group.value, depth + 1) },
      next: group.next,
    };
  }
  const atom = readLeadingAtom(input, i, depth);
  if (!atom) return null;
  return { seg: { type: "cancel", body: atom.body }, next: atom.next };
}

function parseAccent(
  input: string,
  start: number,
  depth: number,
): { seg: MathSegment; next: number } | null {
  const rest = input.slice(start);
  const opener = ACCENT_OPENERS.find((item) => {
    if (!rest.startsWith(item.cmd)) return false;
    const next = rest[item.cmd.length] ?? "";
    return !/[A-Za-z]/.test(next);
  });
  if (!opener) return null;
  let i = start + opener.cmd.length;
  while (input[i] === " ") i += 1;
  const group = readGroup(input, i);
  const body = group
    ? { segments: parseSimpleLatex(group.value, depth + 1), next: group.next }
    : readUnbracedAccentAtom(input, i, depth);
  if (!body) return null;
  return {
    seg: {
      type: "accent",
      kind: opener.kind,
      span: ACCENT_SPAN.has(opener.cmd),
      body: body.segments,
    },
    next: body.next,
  };
}

/** What `^\circ` parses to: a raised ring, which in a superscript is a degree sign. */
export const DEGREE_RING = "∘";

function segmentToPlain(seg: MathSegment): string {
  if (seg.type === "text" || seg.type === "upright") return seg.value;
  if (seg.type === "sup" || seg.type === "sub") {
    if (seg.body) {
      const inner = segmentsToPlain(seg.body);
      return seg.type === "sup" ? `^${inner}` : `_${inner}`;
    }
    if (seg.type === "sup" && seg.value === DEGREE_RING) return "°";
    return seg.type === "sup" ? `^${seg.value}` : `_${seg.value}`;
  }
  if (seg.type === "cancel") return segmentsToPlain(seg.body);
  if (seg.type === "accent") {
    return markEachChar(segmentsToPlain(seg.body), ACCENT_MARK[seg.kind]);
  }
  if (seg.type === "sqrt") {
    // Radicand under a combining overline ("4̅"), not "(4)" in parens — the
    // bar itself delimits what's under the root, closer to how it's drawn
    // on paper. Nested content (a fraction, superscript, …) is flattened
    // to plain text first since there's no way to draw it under a bar too.
    const body = markEachChar(segmentsToPlain(seg.body), "̅");
    const indexText = seg.index ? segmentsToPlain(seg.index) : seg.degree;
    return indexText ? `√[${indexText}]${body}` : `√${body}`;
  }
  return `${segmentsToPlain(seg.num)}/${segmentsToPlain(seg.den)}`;
}

/** `\text{flight}` after a bare `_` or `^` is one upright script.
 * Taking only the private-use start marker made iOS draw it as an emoji
 * and left the closing marker beside the word. */
function readMarkedUpright(input: string, i: number): { value: string; next: number } | null {
  if (input[i] !== NATIVE_UPRIGHT_START_MARKER) return null;
  const end = input.indexOf(NATIVE_UPRIGHT_END_MARKER, i + 1);
  if (end < 0) return null;
  const value = input
    .slice(i + 1, end)
    .split(NATIVE_LITERAL_APOSTROPHE_MARKER).join("'")
    .split(NATIVE_LITERAL_LEFT_BRACE_MARKER).join("{")
    .split(NATIVE_LITERAL_RIGHT_BRACE_MARKER).join("}");
  return { value, next: end + 1 };
}

function literalBraceChar(ch: string | undefined): string | null {
  if (ch === NATIVE_LITERAL_LEFT_BRACE_MARKER) return "{";
  if (ch === NATIVE_LITERAL_RIGHT_BRACE_MARKER) return "}";
  if (ch === NATIVE_LITERAL_APOSTROPHE_MARKER) return "'";
  return null;
}

/** `\max`, `\mathbf{v}`, `\frac{1}{2}`, `\sqrt[3]{8}` — one atom, not one character. */
function readCommandAtom(input: string, i: number): { source: string; next: number } | null {
  if (input[i] !== "\\") return null;
  const match = /^\\([a-zA-Z]+)/.exec(input.slice(i));
  if (!match) {
    if (!input[i + 1]) return null;
    return { source: input.slice(i, i + 2), next: i + 2 };
  }
  const name = match[1] ?? "";
  let head = i + match[0].length;
  if (name === "operatorname" && input[head] === "*") head += 1;
  let j = head;
  while (input[j] === " ") j += 1;
  if (input[j] === "[") {
    const close = input.indexOf("]", j + 1);
    if (close >= 0) {
      j = close + 1;
      while (input[j] === " ") j += 1;
    }
  }
  if (input[j] !== "{") return { source: input.slice(i, head), next: head };
  const wanted = name === "frac" ? 2 : 1;
  let end = j;
  let got = 0;
  while (got < wanted && input[end] === "{") {
    const group = readGroup(input, end);
    if (!group) break;
    end = group.next;
    got += 1;
    if (got < wanted) {
      while (input[end] === " ") end += 1;
    }
  }
  if (got !== wanted) return { source: input.slice(i, head), next: head };
  return { source: input.slice(i, end), next: end };
}

/** `\{...\}` after preprocessing is a real TeX group. Models escape braces
 * that were only grouping (`x^\{2\}`, `\sqrt\{x\}`). An unclosed `\{` stays
 * a visible brace. */
function readMarkerGroup(input: string, start: number): { value: string; next: number } | null {
  if (input[start] !== NATIVE_LITERAL_LEFT_BRACE_MARKER) return null;
  let depth = 1;
  for (let k = start + 1; k < input.length; k += 1) {
    if (input[k] === NATIVE_LITERAL_LEFT_BRACE_MARKER) depth += 1;
    else if (input[k] === NATIVE_LITERAL_RIGHT_BRACE_MARKER) {
      depth -= 1;
      if (depth === 0) return { value: input.slice(start + 1, k), next: k + 1 };
    }
  }
  return null;
}

/** Upright word, escaped brace group, or backslash command. Not a plain letter. */
function readLeadingAtom(
  input: string,
  i: number,
  depth: number,
): { body: MathSegment[]; next: number } | null {
  const marked = readMarkedUpright(input, i);
  if (marked) return { body: [{ type: "upright", value: marked.value }], next: marked.next };
  if (input[i] === NATIVE_LITERAL_LEFT_BRACE_MARKER) {
    const group = readMarkerGroup(input, i);
    if (group) return { body: parseSimpleLatex(group.value, depth + 1), next: group.next };
    return { body: [{ type: "text", value: "{" }], next: i + 1 };
  }
  const brace = literalBraceChar(input[i]);
  if (brace) return { body: [{ type: "text", value: brace }], next: i + 1 };
  if (input[i] !== "\\") return null;
  const atom = readCommandAtom(input, i);
  if (!atom) return null;
  return { body: parseSimpleLatex(atom.source, depth + 1), next: atom.next };
}

/** `\hat x` and `\hat\text{v}` take one atom when the braces were omitted. */
function readUnbracedAccentAtom(
  input: string,
  i: number,
  depth: number,
): { segments: MathSegment[]; next: number } | null {
  const leading = readLeadingAtom(input, i, depth);
  if (leading) return { segments: leading.body, next: leading.next };
  const cp = input.codePointAt(i);
  if (cp == null) return null;
  const ch = String.fromCodePoint(cp);
  if (/[\s^_{}\\]/.test(ch)) return null;
  return { segments: [{ type: "text", value: ch }], next: i + ch.length };
}

function readBareScript(input: string, i: number): { value: string; next: number } {
  if (i >= input.length) return { value: "", next: i };
  let j = i;
  if (input[j] === "+" || input[j] === "-") j += 1;
  if (j < input.length && input[j] >= "0" && input[j] <= "9") {
    while (j < input.length && input[j] >= "0" && input[j] <= "9") j += 1;
    return { value: input.slice(i, j), next: j };
  }
  if (j === i && ((input[j] >= "a" && input[j] <= "z") || (input[j] >= "A" && input[j] <= "Z"))) {
    return { value: input[j] ?? "", next: i + 1 };
  }
  const raw = input[i] ?? "";
  const brace = literalBraceChar(raw);
  if (brace) return { value: brace, next: i + 1 };
  const code = raw.codePointAt(0) ?? 0;
  // A private-use sentinel is never a visible script. iOS draws it as emoji.
  if (code >= 0xe000 && code <= 0xe00f) return { value: "", next: i + 1 };
  return { value: raw, next: i + 1 };
}

export function parseSimpleLatex(latex: string, depth = 0): MathSegment[] {
  if (depth > MAX_MATH_NEST_DEPTH) {
    return [{ type: "text", value: latex }];
  }
  const input = preprocessLatex(latex);
  const out: MathSegment[] = [];
  let i = 0;

  const restoreNativeLiterals = (value: string) => value
    .split(NATIVE_LITERAL_APOSTROPHE_MARKER).join("'")
    .split(NATIVE_LITERAL_LEFT_BRACE_MARKER).join("{")
    .split(NATIVE_LITERAL_RIGHT_BRACE_MARKER).join("}");

  const pushText = (value: string) => {
    value = restoreNativeLiterals(value)
      .split(NATIVE_UPRIGHT_START_MARKER).join("")
      .split(NATIVE_UPRIGHT_END_MARKER).join("");
    if (!value) return;
    const last = out[out.length - 1];
    if (last?.type === "text") last.value += value;
    else out.push({ type: "text", value });
  };

  const pushScript = (kind: "sup" | "sub", inner: MathSegment[]) => {
    const plain = plainScriptPieces(inner);
    out.push(plain == null
      ? { type: kind, value: "", body: inner }
      : { type: kind, value: plain });
  };

  // TeX ignores spaces between `^`/`_` and the atom. One character here used
  // to be a private-use brace or the backslash of `\mathbf` / `\textit`.
  const takeScript = (kind: "sup" | "sub") => {
    i += 1;
    while (input[i] === " ") i += 1;
    const marked = readMarkedUpright(input, i);
    if (marked) {
      out.push({
        type: kind,
        value: "",
        body: [{ type: "upright", value: marked.value }],
      });
      i = marked.next;
      return;
    }
    if (input[i] === "{") {
      const group = readGroup(input, i);
      if (group) {
        pushScript(kind, parseSimpleLatex(group.value, depth + 1));
        i = group.next;
        return;
      }
    }
    const leading = readLeadingAtom(input, i, depth);
    if (leading) {
      pushScript(kind, leading.body);
      i = leading.next;
      return;
    }
    const bare = readBareScript(input, i);
    if (bare.value) out.push({ type: kind, value: bare.value });
    i = bare.next > i ? bare.next : i + 1;
  };

  while (i < input.length) {
    const frac = parseFrac(input, i, depth);
    if (frac) {
      out.push(frac.seg);
      i = frac.next;
      continue;
    }

    const sqrt = parseSqrt(input, i, depth);
    if (sqrt) {
      out.push(sqrt.seg);
      i = sqrt.next;
      continue;
    }

    const cancel = parseCancel(input, i, depth);
    if (cancel) {
      out.push(cancel.seg);
      i = cancel.next;
      continue;
    }

    const accent = parseAccent(input, i, depth);
    if (accent) {
      out.push(accent.seg);
      i = accent.next;
      continue;
    }

    const ch = input[i];

    if (ch === NATIVE_LITERAL_LEFT_BRACE_MARKER) {
      pushText("{");
      i += 1;
      continue;
    }
    if (ch === NATIVE_LITERAL_RIGHT_BRACE_MARKER) {
      pushText("}");
      i += 1;
      continue;
    }

    // Unescaped braces are TeX grouping syntax, not visible glyphs. SymPy
    // emits them around atoms inside scalable delimiters (for example
    // `\\left|{x}\\right|`). Parse their contents recursively so every such
    // expression renders as normal math, while escaped `\\{` / `\\}` still
    // take the literal-character path below for sets.
    if (ch === "{") {
      const group = readGroup(input, i);
      if (group) {
        for (const seg of parseSimpleLatex(group.value, depth + 1)) {
          if (seg.type === "text") pushText(seg.value);
          else out.push(seg);
        }
        i = group.next;
        continue;
      }
    }
    if (ch === "}") {
      i += 1;
      continue;
    }

    if (ch === NATIVE_UPRIGHT_START_MARKER) {
      const end = input.indexOf(NATIVE_UPRIGHT_END_MARKER, i + 1);
      if (end >= 0) {
        out.push({
          type: "upright",
          value: restoreNativeLiterals(input.slice(i + 1, end)),
        });
        i = end + 1;
        continue;
      }
    }

    if (ch === "^" || ch === "_") {
      takeScript(ch === "^" ? "sup" : "sub");
      continue;
    }

    if (ch === "\\") {
      const rest = input.slice(i + 1);
      const cmd = rest.match(/^[a-zA-Z]+/)?.[0];
      if (cmd) {
        // Preserve the operation as readable function notation. Dropping a
        // braced command name made \sin{x} and \log{x} silently become x.
        i += cmd.length + 1;
        let argStart = i;
        while (input[argStart] === " ") argStart += 1;
        if (input[argStart] === "{") {
          const group = readGroup(input, argStart);
          if (group) {
            if (!TEXT_STYLE_COMMANDS.has(cmd)) pushText(`${cmd}(`);
            for (const seg of parseSimpleLatex(group.value, depth + 1)) {
              if (seg.type === "text") pushText(seg.value);
              else out.push(seg);
            }
            if (!TEXT_STYLE_COMMANDS.has(cmd)) pushText(")");
            i = group.next;
          } else {
            pushText(cmd);
          }
        } else {
          pushText(cmd);
        }
        continue;
      }
      // `\|` is a norm bar. U+2016 is not in KaTeX_Main; the renderer draws
      // two `|` glyphs. A single escaped bar stays one `|`.
      if (rest[0] === "|") {
        pushText("‖");
        i += 2;
        continue;
      }
      // `\{` `\%` `\_` — emit the escaped character, not a stray backslash.
      if (rest[0]) {
        pushText(rest[0]);
        i += 2;
        continue;
      }
    }

    pushText(ch);
    i += 1;
  }

  return out.length ? out : [{ type: "text", value: input }];
}

export function segmentsToPlain(segments: MathSegment[]): string {
  return segments.map(segmentToPlain).join("");
}

/**
 * Readable stand-in when KaTeX cannot typeset (parse error, no WebView).
 * Never includes a leftover `\\command` — that is what showed as raw LaTeX.
 */
export function readableLatexFallback(latex: string): string {
  const plain = segmentsToPlain(parseSimpleLatex(latex));
  return plain.replace(/\\[a-zA-Z]+/g, (cmd) => cmd.slice(1));
}

