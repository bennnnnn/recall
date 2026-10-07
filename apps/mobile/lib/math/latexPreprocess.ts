import { normalizeUnicodeScripts } from "@/lib/unicodeSupSub";

import { CMD_REPLACEMENTS } from "@/lib/math/latexCommands";
import { isParenthesizedArgument, readGroup } from "@/lib/math/latexGroups";
import { rewriteSolutionSeparatorBars } from "@/lib/math/solutionBars";
import {
  NATIVE_LITERAL_APOSTROPHE_MARKER,
  NATIVE_LITERAL_LEFT_BRACE_MARKER,
  NATIVE_LITERAL_RIGHT_BRACE_MARKER,
  NATIVE_UPRIGHT_END_MARKER,
  NATIVE_UPRIGHT_START_MARKER,
  UPRIGHT_TEXT_COMMAND_RE,
  UPRIGHT_TEXT_UNWRAP_RE,
  restoreMathEscapes,
} from "@/lib/math/textMarkers";

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

export function preprocessLatex(latex: string): string {
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
  s = s.replace(/\\[dt]?binom\{([^{}]*)\}\{([^{}]*)\}/g, "C($1,$2)");
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

