/** Parse simple LaTeX into native Text segments (no WebView). */

import { normalizeUnicodeScripts } from "@/lib/unicodeSupSub";
import { rewriteSolutionSeparatorBars } from "@/lib/math/solutionBars";

export type MathAccentKind =
  | "overline"
  | "underline"
  | "hat"
  | "tilde"
  | "vec"
  | "vecLeft"
  | "bar"
  | "dot"
  | "ddot";

export type MathSegment =
  | { type: "text"; value: string }
  | { type: "upright"; value: string }
  | { type: "sup"; value: string; body?: MathSegment[] }
  | { type: "sub"; value: string; body?: MathSegment[] }
  | { type: "frac"; num: MathSegment[]; den: MathSegment[] }
  | { type: "sqrt"; body: MathSegment[]; degree?: string; index?: MathSegment[] }
  | { type: "cancel"; body: MathSegment[] }
  | { type: "accent"; kind: MathAccentKind; body: MathSegment[]; span?: boolean };

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
/**
 * `\$` inside math is a dollar sign. Replacing only the backslash leaves a
 * real `$`, and the next scanner closes the span there. The amount then
 * falls out as plain text with the backslash still in front of it.
 */
export const PROTECTED_LITERAL_DOLLAR = String.fromCharCode(0xe00a);
/** Bare `_` inside `$...$` — markdown-it would otherwise start emphasis. */
export const PROTECTED_MATH_UNDERSCORE_MARKER = String.fromCharCode(0xe002);
/** Bare `*` inside `$...$` — markdown-it would otherwise start emphasis. */
export const PROTECTED_MATH_STAR_MARKER = String.fromCharCode(0xe003);
/** Straight math apostrophes must survive Markdown smartquotes unchanged. */
export const PROTECTED_MATH_APOSTROPHE_MARKER = String.fromCharCode(0xe004);
// Native-only literal text/escape preservation across recursive frac parsing.
const NATIVE_LITERAL_APOSTROPHE_MARKER = String.fromCharCode(0xe005);
// Preserve the semantic boundary of \text{...}/\mathrm{...} until native
// rendering. Without this, unit labels became italic variables after the
// dedicated math font was introduced.
const NATIVE_UPRIGHT_START_MARKER = String.fromCharCode(0xe006);
const NATIVE_UPRIGHT_END_MARKER = String.fromCharCode(0xe007);
// Literal set braces must survive the generic TeX-group unwrapping below.
const NATIVE_LITERAL_LEFT_BRACE_MARKER = String.fromCharCode(0xe008);
const NATIVE_LITERAL_RIGHT_BRACE_MARKER = String.fromCharCode(0xe009);
// `\textit` and `\operatorname*` belong with `\text`. Leaving them out let a
// bare `_` keep the backslash and print the command name beside the word.
const UPRIGHT_TEXT_COMMANDS =
  "text|textrm|textsf|texttt|textnormal|textbf|textit|textup|emph|mbox|hbox|mathrm|operatorname";
const UPRIGHT_TEXT_COMMAND_RE = new RegExp(
  `^\\\\(?:${UPRIGHT_TEXT_COMMANDS})\\*?(?![A-Za-z])`,
);
const UPRIGHT_TEXT_UNWRAP_RE = new RegExp(
  `\\\\(?:${UPRIGHT_TEXT_COMMANDS})\\*?\\{([^}]+)\\}`,
  "g",
);

/** Restore source characters after markdown tokenization, before math parsing. */
export function restoreMathEscapes(latex: string): string {
  return latex
    .split(PROTECTED_LITERAL_DOLLAR).join("$")
    .split(PROTECTED_ESCAPE_MARKER).join("\\")
    .split(PROTECTED_MATH_UNDERSCORE_MARKER).join("_")
    .split(PROTECTED_MATH_STAR_MARKER).join("*")
    .split(PROTECTED_MATH_APOSTROPHE_MARKER).join("'");
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
 * The math view sizes itself from the layout tree. This floor is only the
 * markdown line box beside a stacked atom.
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

export type ScriptAttachment = {
  segment: MathSegment;
  index: number;
  sup: Extract<MathSegment, { type: "sup" }> | null;
  sub: Extract<MathSegment, { type: "sub" }> | null;
};

/** A base with both a superscript and a subscript is one script column.
 * A lone script stays attached to the text run so it can live inside Text. */
export function attachScripts(segments: MathSegment[]): ScriptAttachment[] {
  const out: ScriptAttachment[] = [];
  for (let i = 0; i < segments.length; i += 1) {
    const segment = segments[i];
    if (!segment) continue;
    if (segment.type === "sup" || segment.type === "sub") {
      out.push({ segment, index: i, sup: null, sub: null });
      continue;
    }
    let sup: ScriptAttachment["sup"] = null;
    let sub: ScriptAttachment["sub"] = null;
    let j = i + 1;
    while (j < segments.length) {
      const next = segments[j];
      if (next?.type === "sup" && !sup) sup = next;
      else if (next?.type === "sub" && !sub) sub = next;
      else break;
      j += 1;
    }
    if (sup && sub) {
      out.push({ segment, index: i, sup, sub });
      i = j - 1;
    } else {
      out.push({ segment, index: i, sup: null, sub: null });
    }
  }
  return out;
}

export function latexHasNestedMathView(latex: string): boolean {
  const source = restoreMathEscapes(latex);
  if (
    latexHasStackedFrac(source)
    || /\\(?:sqrt|xcancel|bcancel|cancel|overline|underline|widehat|widetilde|overrightarrow|overleftarrow|hat|vec|bar|ddot|dot|tilde)(?![A-Za-z])|\^\{[^{}]*\/[^{}]*\}/.test(
      source,
    )
  ) {
    return true;
  }
  // Superscripts and subscripts shift with translateY. That shift is ignored
  // on a Text nested in Text, so the host has to be a View or `x^2` draws as x2.
  return parseSimpleLatex(source).some((seg) => seg.type === "sup" || seg.type === "sub");
}

const CMD_REPLACEMENTS: [RegExp, string][] = [
  [/\\prime(?![a-zA-Z])/g, "′"],
  [/\\pm(?![a-zA-Z])/g, "±"],
  [/\\mp(?![a-zA-Z])/g, "∓"],
  [/\\times(?![a-zA-Z])/g, "×"],
  // Longest-first: `\cdot` is a prefix of `\cdots`. Without these, a
  // factorial step `$n \times (n-1) \times \cdots \times 1$` rendered as `·s`.
  [/\\cdots(?![a-zA-Z])/g, "⋯"],
  [/\\ldots(?![a-zA-Z])/g, "…"],
  [/\\dots(?![a-zA-Z])/g, "…"],
  // U+22C5 is the KaTeX_Main dot. U+00B7 middle dot is not in that face.
  [/\\cdot(?![a-zA-Z])/g, "⋅"],
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
  // Reduced Planck constant. Without this, `\hbar` falls through as the word hbar.
  [/\\hbar(?![a-zA-Z])/g, "ℏ"],
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
  // Equilibrium arrows: chemistry writes these between species, and the word leaked otherwise.
  [/\\rightleftharpoons(?![a-zA-Z])/g, "⇌"],
  [/\\leftrightharpoons(?![a-zA-Z])/g, "⇋"],
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
  [/\\lceil(?![a-zA-Z])/g, "⌈"],
  [/\\rceil(?![a-zA-Z])/g, "⌉"],
  [/\\lfloor(?![a-zA-Z])/g, "⌊"],
  [/\\rfloor(?![a-zA-Z])/g, "⌋"],
  // Conditional probability / set-builder separator. Without an explicit
  // native mapping the generic command fallback rendered ``\mid`` as the
  // literal word "mid" (for example P(D mid +)).
  [/\\mid(?![a-zA-Z])/g, "∣"],
  [/\\lVert(?![a-zA-Z])/g, "‖"],
  [/\\rVert(?![a-zA-Z])/g, "‖"],
  [/\\Vert(?![a-zA-Z])/g, "‖"],
  // Vertical / bidirectional arrows (rightward/implies already handled).
  [/\\uparrow(?![a-zA-Z])/g, "↑"],
  [/\\downarrow(?![a-zA-Z])/g, "↓"],
  [/\\updownarrow(?![a-zA-Z])/g, "↕"],
  [/\\Updownarrow(?![a-zA-Z])/g, "⇕"],
  [/\\Uparrow(?![a-zA-Z])/g, "⇑"],
  [/\\Downarrow(?![a-zA-Z])/g, "⇓"],
];

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

function readGroup(input: string, start: number): { value: string; next: number } | null {
  if (input[start] !== "{") return null;
  let depth = 0;
  for (let i = start; i < input.length; i += 1) {
    // An escaped brace is visible content, not TeX group structure. Skipping
    // the escaped character also handles odd/even backslash runs correctly.
    if (input[i] === "\\" && i + 1 < input.length) {
      i += 1;
      continue;
    }
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
  Bmatrix: [NATIVE_LITERAL_LEFT_BRACE_MARKER, NATIVE_LITERAL_RIGHT_BRACE_MARKER],
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
 * Native MathText flattens environments into readable rows. Display math
 * does not take this path: MathBlock sends the original LaTeX to MathJax-SVG,
 * which scales the brackets. This fallback exists so a matrix still reads
 * as rows if MathJax cannot parse it.
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

/** Native postfix primes are math glyphs, not prose quotation marks.
 * Keep text-command contents and escaped quotes literal through recursive
 * fraction/root parsing. KaTeX receives only restoreMathEscapes, never this. */
function normalizeNativeDerivativePrimes(source: string): string {
  let out = "";
  for (let i = 0; i < source.length;) {
    if (source[i] === "\\") {
      const textCommand = UPRIGHT_TEXT_COMMAND_RE.exec(source.slice(i));
      if (textCommand) {
        let groupAt = i + textCommand[0].length;
        while (source[groupAt] === " ") groupAt += 1;
        const group = source[groupAt] === "{" ? readGroup(source, groupAt) : null;
        if (group) {
          out += source.slice(i, group.next).replace(/'/g, NATIVE_LITERAL_APOSTROPHE_MARKER);
          i = group.next;
          continue;
        }
        if (source[groupAt] === "{") {
          // An incomplete text group stays literal; do not rescan nested
          // text openers or reinterpret its apostrophes as derivatives.
          out += source.slice(i).replace(/'/g, NATIVE_LITERAL_APOSTROPHE_MARKER);
          break;
        }
      }
      if (source[i + 1] && !/[A-Za-z]/.test(source[i + 1])) {
        out += source.slice(i, i + 2).replace(/'/g, NATIVE_LITERAL_APOSTROPHE_MARKER);
        i += 2;
        continue;
      }
    }
    if (source[i] === "'") {
      let end = i + 1;
      while (source[end] === "'") end += 1;
      const previous = source[i - 1] ?? "";
      let atom = /[0-9)\]}α-ωΑ-Ω]/.test(previous);
      if (/[A-Za-z]/.test(previous)) {
        let wordStart = i - 1;
        while (wordStart > 0 && /[A-Za-z]/.test(source[wordStart - 1])) wordStart -= 1;
        atom = wordStart === i - 1 || source[wordStart - 1] === "\\";
      }
      // A contraction/quoted word is not a mathematical postfix.
      if (atom && !/[A-Za-z]/.test(source[end] ?? "")) {
        const count = end - i;
        out += count === 1 ? "′" : count === 2 ? "″" : count === 3 ? "‴" : "′".repeat(count);
      } else {
        out += source.slice(i, end);
      }
      i = end;
      continue;
    }
    out += source[i];
    i += 1;
  }
  return out;
}

function preserveNativeUprightRuns(source: string): string {
  let out = "";
  for (let i = 0; i < source.length;) {
    if (source[i] === "\\") {
      const command = UPRIGHT_TEXT_COMMAND_RE.exec(source.slice(i));
      if (command) {
        let groupAt = i + command[0].length;
        while (source[groupAt] === " ") groupAt += 1;
        const group = source[groupAt] === "{" ? readGroup(source, groupAt) : null;
        if (group) {
          // TeX ignores a space before \text. The brace holds the visible
          // space (`43 \text{ per hour}`); keeping both shows `43  per`.
          if (/^\s/.test(group.value)) out = out.replace(/ +$/, "");
          // Markdown attaches sentence punctuation to a math run as
          // `\text{.}` / `\text{,}`. Keep that punctuation in the adjacent
          // run so copy, wrapping, and tests see one continuous expression.
          out += /^[\s.,;:!?]+$/.test(group.value)
            ? group.value
            : `${NATIVE_UPRIGHT_START_MARKER}${group.value}${NATIVE_UPRIGHT_END_MARKER}`;
          i = group.next;
          continue;
        }
      }
    }
    out += source[i];
    i += 1;
  }
  return out;
}

/** Unwrap only SymPy's invisible function-argument group, before escaped
 * set braces lose their backslashes. Ordinary brace groups stay unchanged. */
function unwrapSympyFunctionArguments(source: string): string {
  let out = "";
  for (let i = 0; i < source.length;) {
    if (source.startsWith("{\\left(", i) && /[A-Za-z]/.test(source[i - 1] ?? "") &&
      !/[A-Za-z]/.test(source[i - 2] ?? "")) {
      const group = readGroup(source, i);
      if (!group) { out += source.slice(i); break; }
      const body = group.value.trim();
      if (body.startsWith("\\left(") && body.endsWith("\\right)")) {
        const argument = `(${body.slice(6, -7).trim()})`;
        if (isParenthesizedArgument(argument)) {
          out += argument;
          i = group.next;
          continue;
        }
      }
      // A nonmatching complete group remains literal as a whole.
      out += source.slice(i, group.next);
      i = group.next;
      continue;
    }
    out += source[i];
    i += 1;
  }
  return out;
}

function preprocessLatex(latex: string): string {
  let s = normalizeNativeDerivativePrimes(unwrapSympyFunctionArguments(restoreMathEscapes(latex.trim())));
  s = preserveNativeUprightRuns(s);
  // Protect visible set delimiters before command replacement turns `\{`
  // into an ordinary `{`, which is otherwise indistinguishable from an
  // invisible TeX grouping brace. Sized set delimiters are visible too.
  s = s.replace(/\\left\\\{/g, NATIVE_LITERAL_LEFT_BRACE_MARKER);
  s = s.replace(/\\right\\\}/g, NATIVE_LITERAL_RIGHT_BRACE_MARKER);
  s = s.replace(
    /\\[Bb]ig(?:gl|gr|l|r|g)?\\\{/g,
    NATIVE_LITERAL_LEFT_BRACE_MARKER,
  );
  s = s.replace(
    /\\[Bb]ig(?:gl|gr|l|r|g)?\\\}/g,
    NATIVE_LITERAL_RIGHT_BRACE_MARKER,
  );
  s = s.replace(/\\\{/g, NATIVE_LITERAL_LEFT_BRACE_MARKER);
  s = s.replace(/\\\}/g, NATIVE_LITERAL_RIGHT_BRACE_MARKER);
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
  // Nested `\textit` / `\mathrm` inside an upright run is already inside
  // markers. Unwrap the leftover command so the word is not shown raw.
  // One pass misses `\textit{\mathrm{a}}` because the inner `}` blocks the
  // outer match; each pass shrinks the string.
  for (let pass = 0; pass < 4; pass += 1) {
    UPRIGHT_TEXT_UNWRAP_RE.lastIndex = 0;
    const unwrapped = s.replace(UPRIGHT_TEXT_UNWRAP_RE, "$1");
    if (unwrapped === s) break;
    s = unwrapped;
  }
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
  // Accents stay as commands. parseAccent builds a segment whose rule is
  // measured from the child; combining marks are only the copy/speech form.
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

/** SymPy emits y{\\left(x \\right)}; these braces group one function
 * argument and are invisible in TeX. Escaped set braces never enter here. */
function isParenthesizedArgument(value: string): boolean {
  const text = value.trim();
  if (!text.startsWith("(") || !text.endsWith(")")) return false;
  let depth = 0;
  for (let i = 0; i < text.length; i += 1) {
    if (text[i] === "\\") { i += 1; continue; }
    if (text[i] === "(") depth += 1;
    if (text[i] === ")") depth -= 1;
    if (depth === 0 && i < text.length - 1) return false;
  }
  return depth === 0;
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
