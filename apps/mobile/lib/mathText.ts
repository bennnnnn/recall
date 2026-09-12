/** Parse simple LaTeX into native Text segments (no WebView). */

import { normalizeUnicodeScripts } from "@/lib/unicodeSupSub";
import { rewriteSolutionSeparatorBars } from "@/lib/math/solutionBars";

export type MathSegment =
  | { type: "text"; value: string }
  | { type: "sup"; value: string }
  | { type: "sub"; value: string }
  | { type: "frac"; num: MathSegment[]; den: MathSegment[] }
  | { type: "sqrt"; body: MathSegment[]; degree?: string };

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
/** Bare `_` inside `$...$` — markdown-it would otherwise start emphasis. */
export const PROTECTED_MATH_UNDERSCORE_MARKER = String.fromCharCode(0xe002);
/** Bare `*` inside `$...$` — markdown-it would otherwise start emphasis. */
export const PROTECTED_MATH_STAR_MARKER = String.fromCharCode(0xe003);

/** Restore source characters after markdown tokenization, before math parsing. */
export function restoreMathEscapes(latex: string): string {
  return latex
    .split(PROTECTED_ESCAPE_MARKER).join("\\")
    .split(PROTECTED_MATH_UNDERSCORE_MARKER).join("_")
    .split(PROTECTED_MATH_STAR_MARKER).join("*");
}

/** Cap nested \\frac / \\sqrt recursion on pathological model latex. */
const MAX_MATH_NEST_DEPTH = 12;

// These commands change typography, not the operation applied to an argument.
const TEXT_STYLE_COMMANDS = new Set([
  "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathscr", "boldsymbol", "bm",
]);

/**
 * Stacked frac/sqrt need a taller parent `lineHeight` than body prose (16/23).
 * Nested RN Text often keeps the outer line box, so the vinculum kisses the
 * line above unless both MathText and the wrapping markdown Text use this.
 * Must stay ≥ MathText's 44px simple frac stack or the numerator is clipped.
 */
export const MATH_TALL_LINE_HEIGHT = 46;
/** Superscripts (`a^2`, a²) need more leading than body 23 or they clip the line above. */
export const MATH_SCRIPT_LINE_HEIGHT = 34;

/** True when native/inline layout must leave room above/below the run. */
export function latexNeedsTallLine(latex: string): boolean {
  return /\\(?:d|t|c)?frac|\\sqrt/.test(restoreMathEscapes(latex));
}

/** LaTeX superscript/subscript only — Unicode ² / CO₂ in prose must not inflate the paragraph. */
const SUPER_OR_SUB_RE = /\^|_\{/;

/** Line height the wrapping markdown Text must use so math doesn't overlap neighbors. */
export function mathRunLineHeight(latex: string): number | undefined {
  if (latexNeedsTallLine(latex)) {
    // Never shrink below MATH_TALL_LINE_HEIGHT for a stacked frac/sqrt.
    // Passing the whole paragraph (prose + `$...$`) used to trip
    // `length > 48` / multi-stack and return 34, which clips the 40px
    // numerator ("the above numbers can't be seen").
    return MATH_TALL_LINE_HEIGHT;
  }
  if (SUPER_OR_SUB_RE.test(restoreMathEscapes(latex))) return MATH_SCRIPT_LINE_HEIGHT;
  return undefined;
}

/**
 * Stacked `\\frac` / `\\sqrt` is a nested View. Inside a paragraph `Text`
 * that View gets a zero-size text attachment on iOS and paints over
 * neighboring words (the "smudged" line) unless it leaves the text run.
 */
export function latexHasStackedFrac(latex: string): boolean {
  return /\\(?:d|t|c)?frac/.test(restoreMathEscapes(latex));
}

export function latexHasNestedMathView(latex: string): boolean {
  return latexHasStackedFrac(latex) || /\\sqrt|\^\{[^{}]*\/[^{}]*\}/.test(restoreMathEscapes(latex));
}

const CMD_REPLACEMENTS: [RegExp, string][] = [
  [/\\pm(?![a-zA-Z])/g, "±"],
  [/\\mp(?![a-zA-Z])/g, "∓"],
  [/\\times(?![a-zA-Z])/g, "×"],
  // Longest-first: `\cdot` is a prefix of `\cdots`. Without these, a
  // factorial step `$n \times (n-1) \times \cdots \times 1$` rendered as `·s`.
  [/\\cdots(?![a-zA-Z])/g, "⋯"],
  [/\\ldots(?![a-zA-Z])/g, "…"],
  [/\\dots(?![a-zA-Z])/g, "…"],
  [/\\cdot(?![a-zA-Z])/g, "·"],
  // Function composition (f ∘ g) — without this, "$ (f \circ g)(2) $" leaks
  // the literal backslash command in MathText / compact answer pills.
  [/\\circ(?![a-zA-Z])/g, "∘"],
  [/\\div(?![a-zA-Z])/g, "÷"],
  [/\\leq(?![a-zA-Z])/g, "≤"],
  [/\\geq(?![a-zA-Z])/g, "≥"],
  // Short forms — common in homework; without these "$x \le 2$" leaks "\le".
  [/\\le(?![a-zA-Z])/g, "≤"],
  [/\\ge(?![a-zA-Z])/g, "≥"],
  [/\\neq(?![a-zA-Z])/g, "≠"],
  // Short form — models write `$a \ne 0$` as often as `\neq`.
  [/\\ne(?![a-zA-Z])/g, "≠"],
  [/\\not=/g, "≠"],
  [/\\approx(?![a-zA-Z])/g, "≈"],
  [/\\infty(?![a-zA-Z])/g, "∞"],
  [/\\cup(?![a-zA-Z])/g, "∪"],
  [/\\cap(?![a-zA-Z])/g, "∩"],
  // Logical or/and — inequality unions use `\lor` (prompt asks for
  // `$x < -1 \lor x > 1$`); without these MathText leaks raw cmds.
  [/\\lor(?![a-zA-Z])/g, "∨"],
  [/\\vee(?![a-zA-Z])/g, "∨"],
  [/\\land(?![a-zA-Z])/g, "∧"],
  [/\\wedge(?![a-zA-Z])/g, "∧"],
  [/\\setminus(?![a-zA-Z])/g, "∖"],
  [/\\emptyset(?![a-zA-Z])/g, "∅"],
  // Blackboard bold — docs claim native support; without this, steps leak
  // "\mathbb{R}" as raw text (display KaTeX never sees inline $...$).
  [/\\mathbb\{R\}/g, "ℝ"],
  [/\\mathbb\{Z\}/g, "ℤ"],
  [/\\mathbb\{N\}/g, "ℕ"],
  [/\\mathbb\{Q\}/g, "ℚ"],
  [/\\mathbb\{C\}/g, "ℂ"],
  [/\\mathbb\{P\}/g, "ℙ"],
  [/\\mathbb\{H\}/g, "ℍ"],
  [/\\mathbb\{F\}/g, "𝔽"],
  [/\\mathbb\{K\}/g, "𝕂"],
  // \sum/\prod/\int are big-operator SYMBOLS (Σ ∏ ∫), not roman-text
  // function names like \log/\sin — they used to render as the literal
  // words "sum"/"prod"/"int" instead of the actual glyph.
  [/\\sum(?![a-zA-Z])/g, "Σ"],
  [/\\prod(?![a-zA-Z])/g, "∏"],
  [/\\int(?![a-zA-Z])/g, "∫"],
  // Big operators — the "big" variants and the rest of the big-operator family.
  // Without these, \bigcup_{i=1}^n / \oint_C / \iint leaked as the
  // literal words "bigcup"/"oint"/"iint" in inline math.
  [/\\bigcup(?![a-zA-Z])/g, "∪"],
  [/\\bigcap(?![a-zA-Z])/g, "∩"],
  [/\\bigvee(?![a-zA-Z])/g, "∨"],
  [/\\bigwedge(?![a-zA-Z])/g, "∧"],
  [/\\bigoplus(?![a-zA-Z])/g, "⊕"],
  [/\\bigotimes(?![a-zA-Z])/g, "⊗"],
  [/\\bigodot(?![a-zA-Z])/g, "⊙"],
  [/\\biguplus(?![a-zA-Z])/g, "⊎"],
  [/\\oint(?![a-zA-Z])/g, "∮"],
  [/\\iint(?![a-zA-Z])/g, "∬"],
  [/\\iiint(?![a-zA-Z])/g, "∭"],
  [/\\oiint(?![a-zA-Z])/g, "∯"],
  [/\\oiiint(?![a-zA-Z])/g, "⨒"],
  // Base operators not previously handled — leaked as literal names inline.
  [/\\oplus(?![a-zA-Z])/g, "⊕"],
  [/\\otimes(?![a-zA-Z])/g, "⊗"],
  [/\\odot(?![a-zA-Z])/g, "⊙"],
  [/\\uplus(?![a-zA-Z])/g, "⊎"],
  [/\\amalg(?![a-zA-Z])/g, "⨿"],
  // Logic symbols — routine in derivations; leaked as the English words.
  [/\\therefore(?![a-zA-Z])/g, "∴"],
  [/\\because(?![a-zA-Z])/g, "∵"],
  [/\\lnot(?![a-zA-Z])/g, "¬"],
  [/\\neg(?![a-zA-Z])/g, "¬"],
  // \bmod renders as "mod" with math spacing; in plain text use a spaced "mod".
  [/\\bmod(?![a-zA-Z])/g, " mod "],
  // Lowercase Greek letters — matches mathFenceRetag.ts's LATEX_CMD_RE list.
  // Only alpha/beta/gamma/theta/pi were handled here; the rest leaked as
  // raw "\delta"/"\sigma"/etc. backslash text once actually rendered.
  [/\\alpha(?![a-zA-Z])/g, "α"],
  [/\\beta(?![a-zA-Z])/g, "β"],
  [/\\gamma(?![a-zA-Z])/g, "γ"],
  [/\\delta(?![a-zA-Z])/g, "δ"],
  [/\\varepsilon(?![a-zA-Z])/g, "ε"],
  [/\\epsilon(?![a-zA-Z])/g, "ε"],
  [/\\zeta(?![a-zA-Z])/g, "ζ"],
  [/\\eta(?![a-zA-Z])/g, "η"],
  [/\\theta(?![a-zA-Z])/g, "θ"],
  [/\\iota(?![a-zA-Z])/g, "ι"],
  [/\\kappa(?![a-zA-Z])/g, "κ"],
  [/\\lambda(?![a-zA-Z])/g, "λ"],
  [/\\mu(?![a-zA-Z])/g, "μ"],
  [/\\nu(?![a-zA-Z])/g, "ν"],
  [/\\xi(?![a-zA-Z])/g, "ξ"],
  [/\\omicron(?![a-zA-Z])/g, "ο"],
  [/\\pi(?![a-zA-Z])/g, "π"],
  [/\\rho(?![a-zA-Z])/g, "ρ"],
  [/\\sigma(?![a-zA-Z])/g, "σ"],
  [/\\tau(?![a-zA-Z])/g, "τ"],
  [/\\upsilon(?![a-zA-Z])/g, "υ"],
  [/\\phi(?![a-zA-Z])/g, "φ"],
  [/\\chi(?![a-zA-Z])/g, "χ"],
  [/\\psi(?![a-zA-Z])/g, "ψ"],
  [/\\omega(?![a-zA-Z])/g, "ω"],
  [/\\Delta(?![a-zA-Z])/g, "Δ"],
  // Arrow/implication commands — matches mathFenceRetag.ts's LATEX_CMD_RE
  // list. Only the 4 short arrows were handled; the rest (routine in
  // step-by-step derivations and limit notation \lim_{x \to 0}) leaked as
  // raw backslash text.
  [/\\longrightarrow(?![a-zA-Z])/g, "⟶"],
  [/\\rightarrow(?![a-zA-Z])/g, "→"],
  [/\\longleftarrow(?![a-zA-Z])/g, "⟵"],
  [/\\leftarrow(?![a-zA-Z])/g, "←"],
  [/\\Longrightarrow(?![a-zA-Z])/g, "⟹"],
  [/\\Rightarrow(?![a-zA-Z])/g, "⇒"],
  [/\\Longleftarrow(?![a-zA-Z])/g, "⟸"],
  [/\\Leftarrow(?![a-zA-Z])/g, "⇐"],
  [/\\longleftrightarrow(?![a-zA-Z])/g, "⟷"],
  [/\\leftrightarrow(?![a-zA-Z])/g, "↔"],
  [/\\Longleftrightarrow(?![a-zA-Z])/g, "⟺"],
  [/\\Leftrightarrow(?![a-zA-Z])/g, "⇔"],
  [/\\implies(?![a-zA-Z])/g, "⇒"],
  [/\\iff(?![a-zA-Z])/g, "⇔"],
  [/\\to(?![a-zA-Z])/g, "→"],
  [/\\longmapsto(?![a-zA-Z])/g, "⟼"],
  [/\\mapsto(?![a-zA-Z])/g, "↦"],
  [/\\quad(?![a-zA-Z])/g, "  "],
  [/\\qquad(?![a-zA-Z])/g, "    "],
  [/\\displaystyle(?![a-zA-Z])/g, ""],
  [/\\textstyle(?![a-zA-Z])/g, ""],
  [/\\scriptstyle(?![a-zA-Z])/g, ""],
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
  [/\\Gamma(?![a-zA-Z])/g, "Γ"],
  [/\\Theta(?![a-zA-Z])/g, "Θ"],
  [/\\Lambda(?![a-zA-Z])/g, "Λ"],
  [/\\Sigma(?![a-zA-Z])/g, "Σ"],
  [/\\Omega(?![a-zA-Z])/g, "Ω"],
  [/\\Pi(?![a-zA-Z])/g, "Π"],
  [/\\Phi(?![a-zA-Z])/g, "Φ"],
  [/\\Psi(?![a-zA-Z])/g, "Ψ"],
  [/\\Xi(?![a-zA-Z])/g, "Ξ"],
  [/\\Upsilon(?![a-zA-Z])/g, "Υ"],
  // Calculus / set-theory / relation symbols that previously showed raw.
  [/\\partial(?![a-zA-Z])/g, "∂"],
  [/\\nabla(?![a-zA-Z])/g, "∇"],
  [/\\in(?![a-zA-Z])/g, "∈"],
  [/\\notin(?![a-zA-Z])/g, "∉"],
  [/\\subset(?![a-zA-Z])/g, "⊂"],
  [/\\subseteq(?![a-zA-Z])/g, "⊆"],
  [/\\supset(?![a-zA-Z])/g, "⊃"],
  [/\\supseteq(?![a-zA-Z])/g, "⊇"],
  [/\\simeq(?![a-zA-Z])/g, "≃"],
  [/\\cong(?![a-zA-Z])/g, "≅"],
  [/\\equiv(?![a-zA-Z])/g, "≡"],
  [/\\propto(?![a-zA-Z])/g, "∝"],
  [/\\sim(?![a-zA-Z])/g, "∼"],
  [/\\forall(?![a-zA-Z])/g, "∀"],
  [/\\exists(?![a-zA-Z])/g, "∃"],
  [/\\emptyset(?![a-zA-Z])/g, "∅"],
  [/\\angle(?![a-zA-Z])/g, "∠"],
  [/\\degree(?![a-zA-Z])/g, "°"],
  [/\\perp(?![a-zA-Z])/g, "⊥"],
  [/\\parallel(?![a-zA-Z])/g, "∥"],
  // Angle brackets for vectors / inner products — homework dumps
  // `\langle 2,3,4\rangle` constantly; without these MathText leaks raw cmds.
  [/\\langle(?![a-zA-Z])/g, "⟨"],
  [/\\rangle(?![a-zA-Z])/g, "⟩"],
  [/\\lvert(?![a-zA-Z])/g, "|"],
  [/\\rvert(?![a-zA-Z])/g, "|"],
  [/\\lVert(?![a-zA-Z])/g, "‖"],
  [/\\rVert(?![a-zA-Z])/g, "‖"],
  // Vertical / bidirectional arrows (rightward/implies already handled).
  [/\\uparrow(?![a-zA-Z])/g, "↑"],
  [/\\downarrow(?![a-zA-Z])/g, "↓"],
  [/\\updownarrow(?![a-zA-Z])/g, "↕"],
  [/\\Updownarrow(?![a-zA-Z])/g, "⇕"],
  [/\\Uparrow(?![a-zA-Z])/g, "⇑"],
  [/\\Downarrow(?![a-zA-Z])/g, "⇓"],
];

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
  [/\\overrightarrow\{([^{}]+)\}/g, "⃗"],
  [/\\overleftarrow\{([^{}]+)\}/g, "⃖"],
  [/\\vec\{([^{}]+)\}/g, "⃗"], // combining right arrow above
  [/\\ddot\{([^{}]+)\}/g, "̈"], // combining diaeresis (double dot)
  [/\\dot\{([^{}]+)\}/g, "̇"], // combining dot above
  [/\\bar\{([^{}]+)\}/g, "̄"], // combining macron
];

/** Combining mark applied per-character (see ACCENT_COMMANDS above for why
 * per-character, not just the last). Shared with the \sqrt rendering below —
 * a radical's bar has to span its whole radicand the same way \overline's does. */
function markEachChar(text: string, mark: string): string {
  return Array.from(text)
    .map((ch) => (ch === " " ? ch : `${ch}${mark}`))
    .join("");
}

function applyAccentCommands(latex: string): string {
  let s = latex;
  for (const [re, mark] of ACCENT_COMMANDS) {
    s = s.replace(re, (_m, group: string) => markEachChar(group, mark));
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
  smallmatrix: ["", ""],
  Bmatrix: ["{", "}"],
};

const ENV_RE =
  /\\begin\{(cases|matrix|pmatrix|bmatrix|vmatrix|Vmatrix|smallmatrix|Bmatrix|array|aligned|align\*?|gathered|split|multline|eqnarray)\}([\s\S]*?)\\end\{\1\}/g;

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
    // \begin{array}{cc}… — the column spec ({cc}, {c|c}, …) is the first
    // thing in the body and carries no plain-text meaning. Strip a leading
    // braced group before splitting rows, otherwise it leaks as "{cc}" in
    // the first cell.
    let envBody = body;
    if (env === "array" && envBody.trimStart().startsWith("{")) {
      const group = readGroup(envBody, envBody.indexOf("{"));
      if (group) envBody = envBody.slice(group.next);
    }
    const rows = splitEnvRows(envBody);
    if (!rows.length) return "";
    if (env === "cases") {
      // Piecewise: "expr & condition" per row → "expr if condition".
      return rows
        .map(([expr, cond]) => (cond ? `${expr} if ${cond}` : (expr ?? "")))
        .join("; ");
    }
    if (
      env === "aligned" ||
      env === "array" ||
      env === "gathered" ||
      env === "split" ||
      env === "multline" ||
      env === "eqnarray" ||
      env.startsWith("align")
    ) {
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
  let s = restoreMathEscapes(latex.trim());
  // Undo markdownPreprocess.ts's PROTECTED_ESCAPE_MARKER substitution first,
  // before any command table below runs — see the marker's own doc comment.
  s = rewriteSolutionSeparatorBars(s);
  // OCR / models often emit Unicode supers/subs (`x²`, `a₁₀`) instead of
  // caret form. Rewrite to `^`/`_` so the segment parser builds real scripts.
  s = normalizeUnicodeScripts(s);
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
  // \sqrt{...} is handled by parseSqrt below (in the character-by-character
  // parser, not here) — a flat regex over `[^}]+` can't track nested braces,
  // so `\sqrt{\frac{M}{2}}` broke on the FIRST `}` (the one closing \frac's
  // own `{M}`), leaking the rest of the radicand as raw text. readGroup
  // already solves this correctly for \frac's num/den; \sqrt reuses it.
  s = s.replace(/\\text\{([^}]+)\}/g, "$1");
  s = s.replace(/\\mathrm\{([^}]+)\}/g, "$1");
  s = s.replace(/\\operatorname\{([^}]+)\}/g, "$1");
  s = s.replace(/\\overbrace\{([^}]+)\}/g, "$1");
  s = s.replace(/\\underbrace\{([^}]+)\}/g, "$1");
  s = s.replace(/\\substack\{([^{}]+)\}/g, (_m, body: string) =>
    // \substack{a\\b\\c} stacks rows (used under \sum/\prod). Native layout
    // can't stack vertically, so join the rows with "; " — without this the
    // bare unwrap left the "\\" row separator, which then leaked as a stray
    // backslash ("\b") in the next cell.
    body
      .split("\\\\")
      .map((r) => r.trim())
      .filter(Boolean)
      .join("; "),
  );
  // \boxed{...} has no plain-text equivalent (KaTeX/MathJax draw an actual
  // border) — unwrap to the inner content rather than leave the raw command
  // visible, matching \text/\mathrm's fallback above.
  s = s.replace(/\\boxed\{([^}]+)\}/g, "$1");
  // \overset{x}{base} / \underset{x}{base} / \stackrel{x}{base} stack x over
  // or under base — native inline layout can't draw that, so unwrap to the
  // base alone. Runs AFTER \text/\mathrm unwrap so an overset arg written as
  // \overset{\text{def}}{=} is flattened to \overset{def}{=} first, which the
  // single-brace regex below can then match (otherwise the nested braces in
  // \text{def} defeat `[^{}]+` and the overset never unwraps).
  s = s.replace(/\\(?:overset|underset|stackrel)\{[^{}]+\}\{([^{}]+)\}/g, "$1");
  // \color{name}{base} / \textcolor{name}{base} — color has no plain-text
  // meaning; unwrap to the base so the color name ("red") doesn't leak as
  // literal text followed by bare braces.
  s = s.replace(/\\(?:textcolor|color)\{[^{}]+\}\{([^{}]+)\}/g, "$1");
  // \pmod{x} → "(mod x)" (KaTeX renders parenthesized mod). Must run after
  // \pm → ± (in CMD_REPLACEMENTS) so \pm's word boundary lets \pmod survive.
  s = s.replace(/\\pmod\{([^{}]+)\}/g, "(mod $1)");
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
  // After \langle→⟨ / \lvert→| (etc.) above, strip sized wrappers so
  // `\left\langle … \right\rangle` doesn't leak a bare `\left`/`\right`.
  s = s.replace(/\\left(?=[⟨⌈⌊|‖])/g, "");
  s = s.replace(/\\right(?=[⟩⌉⌋|‖])/g, "");
  // Sized delimiters \bigl( \bigr) \Bigl[ \biggl\{ … and the dot form
  // \bigl. behave like \left/\right — they wrap the following delimiter
  // (or "." for an invisible boundary). Strip the command word so the
  // delimiter itself shows; without this the generic \cmd handler kept
  // "bigl"/"bigr"/"Bigl" as literal text ("\bigl(x+1\bigr)" → "bigl(x+1bigr)").
  // The big-operator words (\bigcup etc.) are already replaced above, so a
  // trailing-letter guard isn't needed here — only \big*/\Big* sizing words
  // remain at this point.
  s = s.replace(/\\[Bb]ig(?:gl|gr|l|r|g)?\.?(?![a-zA-Z])/g, "");
  return s;
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
  if (input[i] === "[") {
    const close = input.indexOf("]", i);
    if (close === -1) return null;
    degree = input.slice(i + 1, close);
    i = close + 1;
  }
  while (input[i] === " ") i += 1;
  const group = readGroup(input, i);
  if (group) {
    return {
      seg: { type: "sqrt", body: parseSimpleLatex(group.value, depth + 1), degree },
      next: group.next,
    };
  }
  // \sqrt without braces (\sqrt4, \sqrt 4) — bare single-token radicand.
  const bare = input.slice(i).match(/^[0-9a-zA-Z]+/)?.[0];
  if (bare) {
    return { seg: { type: "sqrt", body: [{ type: "text", value: bare }], degree }, next: i + bare.length };
  }
  return null;
}

function segmentToPlain(seg: MathSegment): string {
  if (seg.type === "text") return seg.value;
  if (seg.type === "sup") return `^${seg.value}`;
  if (seg.type === "sub") return `_${seg.value}`;
  if (seg.type === "sqrt") {
    // Radicand under a combining overline ("4̅"), not "(4)" in parens — the
    // bar itself delimits what's under the root, closer to how it's drawn
    // on paper. Nested content (a fraction, superscript, …) is flattened
    // to plain text first since there's no way to draw it under a bar too.
    const body = markEachChar(segmentsToPlain(seg.body), "̅");
    return seg.degree ? `√[${seg.degree}]${body}` : `√${body}`;
  }
  return `${segmentsToPlain(seg.num)}/${segmentsToPlain(seg.den)}`;
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
  return { value: input[i] ?? "", next: i + 1 };
}

export function parseSimpleLatex(latex: string, depth = 0): MathSegment[] {
  if (depth > MAX_MATH_NEST_DEPTH) {
    return [{ type: "text", value: latex }];
  }
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

    const ch = input[i];

    if (ch === "^") {
      i += 1;
      if (input[i] === "{") {
        const group = readGroup(input, i);
        if (group) {
          out.push({
            type: "sup",
            value: parseSimpleLatex(group.value, depth + 1).map(segmentToPlain).join(""),
          });
          i = group.next;
          continue;
        }
      }
      const bare = readBareScript(input, i);
      out.push({ type: "sup", value: bare.value });
      i = bare.next;
      continue;
    }

    if (ch === "_") {
      i += 1;
      if (input[i] === "{") {
        const group = readGroup(input, i);
        if (group) {
          out.push({
            type: "sub",
            value: parseSimpleLatex(group.value, depth + 1).map(segmentToPlain).join(""),
          });
          i = group.next;
          continue;
        }
      }
      const bare = readBareScript(input, i);
      out.push({ type: "sub", value: bare.value });
      i = bare.next;
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
