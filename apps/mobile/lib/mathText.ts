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
  // \sum/\prod/\int are big-operator SYMBOLS (Σ ∏ ∫), not roman-text
  // function names like \log/\sin — they used to be lumped into
  // ROMAN_FUNCTIONS below and rendered as the literal words "sum"/"prod"/
  // "int" instead of the actual glyph.
  [/\\sum/g, "Σ"],
  [/\\prod/g, "∏"],
  [/\\int/g, "∫"],
  // Lowercase Greek letters — matches mathFenceRetag.ts's LATEX_CMD_RE list.
  // Only alpha/beta/gamma/theta/pi were handled here; the rest leaked as
  // raw "\delta"/"\sigma"/etc. backslash text once actually rendered.
  [/\\alpha/g, "α"],
  [/\\beta/g, "β"],
  [/\\gamma/g, "γ"],
  [/\\delta/g, "δ"],
  [/\\epsilon/g, "ε"],
  [/\\zeta/g, "ζ"],
  [/\\eta/g, "η"],
  [/\\theta/g, "θ"],
  [/\\iota/g, "ι"],
  [/\\kappa/g, "κ"],
  [/\\lambda/g, "λ"],
  [/\\mu/g, "μ"],
  [/\\nu/g, "ν"],
  [/\\xi/g, "ξ"],
  [/\\omicron/g, "ο"],
  [/\\pi/g, "π"],
  [/\\rho/g, "ρ"],
  [/\\sigma/g, "σ"],
  [/\\tau/g, "τ"],
  [/\\upsilon/g, "υ"],
  [/\\phi/g, "φ"],
  [/\\chi/g, "χ"],
  [/\\psi/g, "ψ"],
  [/\\omega/g, "ω"],
  [/\\Delta/g, "Δ"],
  // Arrow/implication commands — matches mathFenceRetag.ts's LATEX_CMD_RE
  // list. Only the 4 short arrows were handled; the rest (routine in
  // step-by-step derivations and limit notation \lim_{x \to 0}) leaked as
  // raw backslash text.
  [/\\longrightarrow/g, "⟶"],
  [/\\rightarrow/g, "→"],
  [/\\longleftarrow/g, "⟵"],
  [/\\leftarrow/g, "←"],
  [/\\Longrightarrow/g, "⟹"],
  [/\\Rightarrow/g, "⇒"],
  [/\\Longleftarrow/g, "⟸"],
  [/\\Leftarrow/g, "⇐"],
  [/\\longleftrightarrow/g, "⟷"],
  [/\\leftrightarrow/g, "↔"],
  [/\\Longleftrightarrow/g, "⟺"],
  [/\\Leftrightarrow/g, "⇔"],
  [/\\implies/g, "⇒"],
  [/\\iff/g, "⇔"],
  [/\\to/g, "→"],
  [/\\longmapsto/g, "⟼"],
  [/\\mapsto/g, "↦"],
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

/** Roman-type function names — render as their bare name (e.g. \log → "log"),
 * matching mathFenceRetag.ts's LATEX_CMD_RE list. Without this, any command
 * not in CMD_REPLACEMENTS above falls through to the generic \cmd fallback
 * and shows the literal backslash (e.g. "\log_2(2)" instead of "log2(2)"). */
const ROMAN_FUNCTIONS = new Set([
  "log",
  "ln",
  "exp",
  "lim",
  "sup",
  "inf",
  "sin",
  "cos",
  "tan",
  "sec",
  "csc",
  "cot",
  "arcsin",
  "arccos",
  "arctan",
  "sinh",
  "cosh",
  "tanh",
  "det",
  "gcd",
  "min",
  "max",
  "arg",
  "deg",
  "ker",
  "dim",
  "hom",
]);

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
  // \boxed{...} has no plain-text equivalent (KaTeX/MathJax draw an actual
  // border) — unwrap to the inner content rather than leave the raw command
  // visible, matching \text/\mathrm's fallback above.
  s = s.replace(/\\boxed\{([^}]+)\}/g, "$1");
  s = s.replace(/\\,/g, " ");
  // Two real alternatives, not one merged character class: the previous
  // `/\\left[\(\[\{|\\right[\)\]\}.]/` compiled everything after the first
  // `[` into a single class, so `\right` never matched at all and left a
  // dangling "\right)" behind (e.g. `\left(\frac{1}{2}\right)`).
  s = s.replace(/\\left([([{|]|\.)/g, (_m, ch: string) => (ch === "." ? "" : ch));
  s = s.replace(/\\right([)\]}|]|\.)/g, (_m, ch: string) => (ch === "." ? "" : ch));
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
        pushText(ROMAN_FUNCTIONS.has(cmd.toLowerCase()) ? cmd : `\\${cmd}`);
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
