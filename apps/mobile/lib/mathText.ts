/** Parse simple LaTeX into native Text segments (no WebView). */

export type MathSegment =
  | { type: "text"; value: string }
  | { type: "sup"; value: string }
  | { type: "sub"; value: string }
  | { type: "frac"; num: string; den: string };

const CMD_REPLACEMENTS: [RegExp, string][] = [
  [/\\pm/g, "±"],
  [/\\mp/g, "∓"],
  [/\\times/g, "×"],
  [/\\cdot/g, "·"],
  [/\\div/g, "÷"],
  [/\\leq/g, "≤"],
  [/\\geq/g, "≥"],
  [/\\neq/g, "≠"],
  [/\\approx/g, "≈"],
  [/\\infty/g, "∞"],
  [/\\pi/g, "π"],
  [/\\theta/g, "θ"],
  [/\\alpha/g, "α"],
  [/\\beta/g, "β"],
  [/\\gamma/g, "γ"],
  [/\\Delta/g, "Δ"],
  [/\\rightarrow/g, "→"],
  [/\\leftarrow/g, "←"],
  [/\\Rightarrow/g, "⇒"],
  [/\\Leftarrow/g, "⇐"],
  [/\\quad/g, "  "],
  [/\\,/g, " "],
  [/\\;/g, " "],
  [/\\!/g, ""],
  [/\\ /g, " "],
  [/\\%/g, "%"],
  [/\\#/g, "#"],
  [/\\&/g, "&"],
  [/\\_/g, "_"],
  [/\\\{/g, "{"],
  [/\\\}/g, "}"],
];

function readGroup(input: string, start: number): { value: string; next: number } | null {
  if (input[start] !== "{") return null;
  let depth = 0;
  for (let i = start; i < input.length; i += 1) {
    if (input[i] === "{") depth += 1;
    else if (input[i] === "}") {
      depth -= 1;
      if (depth === 0) {
        return { value: input.slice(start + 1, i), next: i + 1 };
      }
    }
  }
  return null;
}

function preprocessLatex(latex: string): string {
  let s = latex.trim();
  for (const [re, rep] of CMD_REPLACEMENTS) {
    s = s.replace(re, rep);
  }
  s = s.replace(/\\sqrt\{([^}]+)\}/g, "√($1)");
  s = s.replace(/\\sqrt\s+([0-9a-zA-Z]+)/g, "√$1");
  s = s.replace(/\\text\{([^}]+)\}/g, "$1");
  s = s.replace(/\\mathrm\{([^}]+)\}/g, "$1");
  s = s.replace(/\\,/g, " ");
  s = s.replace(/\\left[\(\[\{|\\right[\)\]\}.]/g, (m) => {
    const ch = m.slice(-1);
    return ch === "." ? "" : ch;
  });
  return s;
}

function parseFrac(input: string, start: number): { seg: MathSegment; next: number } | null {
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
      num: parseSimpleLatex(numGroup.value).map(segmentToPlain).join(""),
      den: parseSimpleLatex(denGroup.value).map(segmentToPlain).join(""),
    },
    next: denGroup.next,
  };
}

function segmentToPlain(seg: MathSegment): string {
  if (seg.type === "text") return seg.value;
  if (seg.type === "sup") return `^${seg.value}`;
  if (seg.type === "sub") return `_${seg.value}`;
  return `${seg.num}/${seg.den}`;
}

export function parseSimpleLatex(latex: string): MathSegment[] {
  const input = preprocessLatex(latex);
  const out: MathSegment[] = [];
  let i = 0;

  const pushText = (value: string) => {
    if (!value) return;
    const last = out[out.length - 1];
    if (last?.type === "text") last.value += value;
    else out.push({ type: "text", value });
  };

  while (i < input.length) {
    const frac = parseFrac(input, i);
    if (frac) {
      out.push(frac.seg);
      i = frac.next;
      continue;
    }

    const ch = input[i];

    if (ch === "^") {
      i += 1;
      if (input[i] === "{") {
        const group = readGroup(input, i);
        if (group) {
          out.push({ type: "sup", value: parseSimpleLatex(group.value).map(segmentToPlain).join("") });
          i = group.next;
          continue;
        }
      }
      out.push({ type: "sup", value: input[i] ?? "" });
      i += 1;
      continue;
    }

    if (ch === "_") {
      i += 1;
      if (input[i] === "{") {
        const group = readGroup(input, i);
        if (group) {
          out.push({ type: "sub", value: parseSimpleLatex(group.value).map(segmentToPlain).join("") });
          i = group.next;
          continue;
        }
      }
      out.push({ type: "sub", value: input[i] ?? "" });
      i += 1;
      continue;
    }

    if (ch === "\\") {
      const rest = input.slice(i + 1);
      const cmd = rest.match(/^[a-zA-Z]+/)?.[0];
      if (cmd) {
        pushText(`\\${cmd}`);
        i += cmd.length + 1;
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
 * Split a math fence body into individual display lines. A single
 * `renderToString`/parse call on a multi-line body concatenates every line
 * into one expression with no separator (no `\n` handling in LaTeX or in
 * our simple parser) — e.g. "x^2 = 5 - 1\nx^2 = 4" renders as the
 * nonsensical "x^2 = 5 - 1x^2 = 4". Each line must be rendered as its own
 * block instead.
 */
export function splitMathLines(latex: string): string[] {
  return latex
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}
