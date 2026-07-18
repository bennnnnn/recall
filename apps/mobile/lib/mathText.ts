/** Parse simple LaTeX into native Text segments (no WebView). */

export type MathSegment =
  | { type: "text"; value: string }
  | { type: "sup"; value: string }
  | { type: "sub"; value: string }
  | { type: "frac"; num: MathSegment[]; den: MathSegment[] };

/**
 * Placeholder for a backslash inside `$...$` / `\(...\)` math that
 * markdownPreprocess.ts substitutes in *before* the content reaches
 * markdown-it. CommonMark's own backslash-escape rule fires on "\" followed
 * by any ASCII punctuation character and silently drops the backslash
 * (e.g. "\," becomes a bare "," — a stray comma sitting where an invisible
 * thin-space belongs; "\!" becomes a bare "!" mid-formula) before this
 * module's CMD_REPLACEMENTS table below ever sees the command. A Private
 * Use Area character isn't ASCII punctuation, so markdown-it's escape rule
 * (and its typographer/smartquotes rules) leave it alone; preprocessLatex
 * decodes it back to a literal backslash as its first step, before any
 * command table runs.
 */
export const PROTECTED_ESCAPE_MARKER = String.fromCharCode(0xe000);

const CMD_REPLACEMENTS: [RegExp, string][] = [
  [/\\pm/g, "±"],
  [/\\mp/g, "∓"],
  [/\\times/g, "×"],
  [/\\cdot/g, "·"],
  // Function composition (f ∘ g) — without this, "$ (f \circ g)(2) $" leaks
  // the literal backslash command in MathText / compact answer pills.
  [/\\circ(?![a-zA-Z])/g, "∘"],
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
  // Uppercase Greek — only \Delta was handled; the rest (\Gamma, \Theta, …)
  // leaked as raw "\Gamma" inline. Matches mathFenceRetag's LATEX_CMD_RE list.
  [/\\Gamma/g, "Γ"],
  [/\\Theta/g, "Θ"],
  [/\\Lambda/g, "Λ"],
  [/\\Sigma/g, "Σ"],
  [/\\Omega/g, "Ω"],
  [/\\Pi/g, "Π"],
  [/\\Phi/g, "Φ"],
  [/\\Psi/g, "Ψ"],
  [/\\Xi/g, "Ξ"],
  [/\\Upsilon/g, "Υ"],
  // Calculus / set-theory / relation symbols that previously showed raw.
  [/\\partial/g, "∂"],
  [/\\nabla/g, "∇"],
  [/\\in/g, "∈"],
  [/\\subset/g, "⊂"],
  [/\\subseteq/g, "⊆"],
  [/\\supset/g, "⊃"],
  [/\\equiv/g, "≡"],
  [/\\propto/g, "∝"],
  [/\\sim/g, "∼"],
  [/\\forall/g, "∀"],
  [/\\exists/g, "∃"],
  [/\\emptyset/g, "∅"],
  [/\\angle/g, "∠"],
  [/\\perp/g, "⊥"],
  [/\\parallel/g, "∥"],
  // Vertical / bidirectional arrows (rightward/implies already handled).
  [/\\uparrow/g, "↑"],
  [/\\downarrow/g, "↓"],
  [/\\updownarrow/g, "↕"],
  [/\\Updownarrow/g, "⇕"],
  [/\\Uparrow/g, "⇑"],
  [/\\Downarrow/g, "⇓"],
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

// Accent commands, mapped to the Unicode combining mark that reproduces them
// in plain text — applied to EVERY character of the group (not just the
// last) so a multi-character span like "714285" gets a continuous line
// across it ("7̅1̅4̅2̅8̅5̅"), matching how \overline actually typesets rather
// than accenting only the final digit. \hat/\vec/\bar/\dot conventionally
// accent a single symbol, but combining marks compose fine over more.
// Longest-alias-first so `\widehat`/`\widetilde` aren't cut short by a
// naive `\hat`/`\tilde` prefix match.
const ACCENT_COMMANDS: [RegExp, string][] = [
  [/\\overline\{([^{}]+)\}/g, "̅"], // combining overline
  [/\\underline\{([^{}]+)\}/g, "̲"], // combining low line
  [/\\widehat\{([^{}]+)\}/g, "̂"], // combining circumflex accent
  [/\\hat\{([^{}]+)\}/g, "̂"],
  [/\\widetilde\{([^{}]+)\}/g, "̃"], // combining tilde
  [/\\tilde\{([^{}]+)\}/g, "̃"],
  [/\\vec\{([^{}]+)\}/g, "⃗"], // combining right arrow above
  [/\\ddot\{([^{}]+)\}/g, "̈"], // combining diaeresis (double dot)
  [/\\dot\{([^{}]+)\}/g, "̇"], // combining dot above
  [/\\bar\{([^{}]+)\}/g, "̄"], // combining macron
];

function applyAccentCommands(latex: string): string {
  let s = latex;
  for (const [re, mark] of ACCENT_COMMANDS) {
    s = s.replace(re, (_m, group: string) =>
      Array.from(group)
        .map((ch) => (ch === " " ? ch : `${ch}${mark}`))
        .join(""),
    );
  }
  return s;
}

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

// Bracket glyphs for the matrix-family environments — "" (matrix) draws no
// bracket at all, matching how KaTeX renders each variant.
const ENV_BRACKETS: Record<string, [string, string]> = {
  matrix: ["", ""],
  pmatrix: ["(", ")"],
  bmatrix: ["[", "]"],
  vmatrix: ["|", "|"],
  Vmatrix: ["‖", "‖"],
};

const ENV_RE = /\\begin\{(cases|matrix|pmatrix|bmatrix|vmatrix|Vmatrix|array|aligned|align\*?)\}([\s\S]*?)\\end\{\1\}/g;

/** Split a LaTeX environment body into rows ("\\" is the row separator) and
 * cells within a row ("&" is the column/alignment separator), trimming each. */
function splitEnvRows(body: string): string[][] {
  return body
    .split("\\\\")
    .map((row) => row.trim())
    .filter(Boolean)
    .map((row) => row.split("&").map((cell) => cell.trim()));
}

/**
 * BUG FIX: `\begin{cases}`/`\begin{matrix}`/… have no entry anywhere in this
 * module — MathBlock deliberately renders the whole environment through this
 * native parser (not KaTeX) whenever the preview WebView is unavailable
 * (Expo Go / no dev build), so a piecewise function or a system written as a
 * matrix rendered as literal "\begin{cases}2x+y=5\\x-y=1\end{cases}" raw
 * text instead of a readable block. Expand each environment into plain,
 * readable text BEFORE any other substitution runs, so the raw "\\"/"&"
 * structural separators are still intact to split on — everything inside a
 * cell (\frac, Greek letters, …) is left untouched here and still gets
 * processed normally by the rest of preprocessLatex afterward.
 */
function expandLatexEnvironments(latex: string): string {
  return latex.replace(ENV_RE, (_match, env: string, body: string) => {
    const rows = splitEnvRows(body);
    if (!rows.length) return "";
    if (env === "cases") {
      // Piecewise: "expr & condition" per row → "expr if condition".
      return rows
        .map(([expr, cond]) => (cond ? `${expr} if ${cond}` : (expr ?? "")))
        .join("; ");
    }
    if (env === "aligned" || env === "array" || env.startsWith("align")) {
      // Alignment columns carry no visible meaning outside KaTeX's layout —
      // just join the cells with a space and each row with a separator.
      return rows.map((cells) => cells.join(" ")).join(";  ");
    }
    const [open, close] = ENV_BRACKETS[env] ?? ["[", "]"];
    const matrixRows = rows.map((cells) => cells.join(", "));
    return `${open}${matrixRows.join("; ")}${close}`;
  });
}

function preprocessLatex(latex: string): string {
  let s = latex.trim();
  // Undo markdownPreprocess.ts's PROTECTED_ESCAPE_MARKER substitution first,
  // before any command table below runs — see the marker's own doc comment.
  if (s.includes(PROTECTED_ESCAPE_MARKER)) {
    s = s.split(PROTECTED_ESCAPE_MARKER).join("\\");
  }
  // Must run before every other substitution — it depends on the raw "\\"
  // row separator and "&" column separator, which later rules (e.g. the
  // \\, → " " spacing rule) would otherwise destroy.
  s = expandLatexEnvironments(s);
  // \binom{n}{k} (and \dbinom/\tbinom, display/text variants) has no visual
  // stacked-column equivalent in plain text — render as the unambiguous
  // "C(n,k)" combinations notation instead of leaking the raw command.
  s = s.replace(/\\[dt]?binom\{([^{}]+)\}\{([^{}]+)\}/g, "C($1,$2)");
  // \dfrac / \tfrac / \cfrac are display/text-style fractions — KaTeX treats
  // them like \frac, so normalize before parsing so parseFrac catches them
  // (otherwise they leak as raw "\dfrac{a}{b}" inline).
  s = s.replace(/\\[dct]frac/g, "\\frac");
  for (const [re, rep] of CMD_REPLACEMENTS) {
    s = s.replace(re, rep);
  }
  // nth-root: \sqrt[n]{x} → √[n](x) (plain but readable). Before the bare
  // \sqrt{...} rule so the [n] isn't dropped.
  s = s.replace(/\\sqrt\[([^\]]+)\]\{([^}]+)\}/g, "√[$1]($2)");
  s = s.replace(/\\sqrt\{([^}]+)\}/g, "√($1)");
  s = s.replace(/\\sqrt\s+([0-9a-zA-Z]+)/g, "√$1");
  s = s.replace(/\\text\{([^}]+)\}/g, "$1");
  s = s.replace(/\\mathrm\{([^}]+)\}/g, "$1");
  // \boxed{...} has no plain-text equivalent (KaTeX/MathJax draw an actual
  // border) — unwrap to the inner content rather than leave the raw command
  // visible, matching \text/\mathrm's fallback above.
  s = s.replace(/\\boxed\{([^}]+)\}/g, "$1");
  // \overline{714285} etc. (repeating decimals, line segments, vectors, …)
  // had no entry anywhere in this table — they fell through to the generic
  // \cmd fallback below, which only consumes the command NAME, leaving the
  // "{714285}" group behind as literal visible text (e.g. the raw
  // "0.\overline{714285}" seen in production). Map to the matching Unicode
  // combining mark instead, same "real glyph over raw command" preference
  // superscript/subscript already use.
  s = applyAccentCommands(s);
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
      // Keep num/den as parsed segments (not flattened strings) so the
      // renderer can render superscripts/subscripts/fractions INSIDE a
      // fraction — \frac{x^2}{4} shows x² in the numerator, not literal "x^2".
      num: parseSimpleLatex(numGroup.value),
      den: parseSimpleLatex(denGroup.value),
    },
    next: denGroup.next,
  };
}

function segmentToPlain(seg: MathSegment): string {
  if (seg.type === "text") return seg.value;
  if (seg.type === "sup") return `^${seg.value}`;
  if (seg.type === "sub") return `_${seg.value}`;
  return `${segmentsToPlain(seg.num)}/${segmentsToPlain(seg.den)}`;
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
  // A multi-line LaTeX environment (\begin{aligned}…\end{aligned}, cases,
  // matrix, gather, …) uses newlines BETWEEN its rows and MUST render as one
  // block — splitting it makes each row a standalone KaTeX parse that errors
  // or renders garbage. So if the body contains any \begin{…}, don't split.
  if (/\\begin\{[\w*]+\}/.test(latex)) {
    return [latex.trim()].filter(Boolean);
  }
  return latex
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}
