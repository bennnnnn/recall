/** Turn model output like `( x^2 = 6 )` or `x2+2=6` into renderable LaTeX. */

const LATEX_CMD = /\\(?:[a-zA-Z]+|.){1,}/;
const MATH_IN_PARENS_RE = /\(\s*([^()\n]{1,180}?)\s*\)/g;
const FENCE_RE = /```[\s\S]*?```/g;

const BARE_EQUATION_RE = /^[0-9a-zA-Z+\-*/^=±√\\_.\s]+$/i;

export function fixImplicitExponents(expr: string): string {
  let s = expr.trim();
  if (!s) return s;

  s = s.replace(/([a-zA-Z])([0-9]+)(?=[+\-=)\]|,\s]|$)/g, "$1^$2");
  s = s.replace(/^(\d)(\d)(?=[+\-*/=])/, "$1^$2");
  s = s.replace(/(\s)(\d)(\d)(?=[+\-*/=])/g, "$1$2^$3");
  if (s.includes("±") && !s.includes("\\pm")) {
    s = s.replace(/±\s*/g, "\\pm ");
  }
  return s.replace(/\s+/g, " ").trim();
}

function isMathLike(inner: string): boolean {
  const s = fixImplicitExponents(inner);
  if (s.length < 2) return false;
  // BARE_EQUATION_RE's char class allows `*` for multiplication, which also
  // matches markdown's `**bold**`/`__bold__` markers — without this guard a
  // prose line like "**Solve** 2^x + 5 = 7" gets misread as a bare equation
  // and wrapped whole in `$...$`, corrupting the bold markdown (the math
  // renderer displays raw source text, not parsed markdown emphasis).
  if (/\*\*|__/.test(s)) return false;
  if (LATEX_CMD.test(s)) return true;
  if (/\^|_[{0-9a-zA-Z]/.test(s)) return true;
  if (/[±√∓≤≥≠]|\\pm/.test(s)) return true;
  if (!/[=<>]/.test(s)) return false;
  if (!BARE_EQUATION_RE.test(s)) return false;
  return /[+\-*/^\\=]/.test(s);
}

function looksLikeBareEquation(line: string): boolean {
  const s = fixImplicitExponents(line.trim());
  if (!/=/.test(s)) return false;
  return BARE_EQUATION_RE.test(s) && isMathLike(s);
}

function unwrapParens(expr: string): string {
  const s = expr.trim();
  const m = s.match(/^\(\s*([\s\S]+?)\s*\)$/);
  return m ? m[1].trim() : s;
}

function wrapMath(expr: string): string {
  return `$${fixImplicitExponents(unwrapParens(expr))}$`;
}

function normalizeMathLine(line: string): string {
  if (/\]\(https?:\/\//.test(line) || /\[places\s*\n/i.test(line)) {
    return line;
  }
  let out = line;

  const equationLabel = out.match(
    /^(\s*(?:\*\*)?(?:Given\s+)?(?:Equation|equation)(?:\*\*)?\s*:\s*)(.+)$/i,
  );
  if (equationLabel) {
    const expr = equationLabel[2].trim();
    if (isMathLike(expr) || looksLikeBareEquation(expr)) {
      return `${equationLabel[1]}${wrapMath(expr)}`;
    }
  }

  const verifyLabel = out.match(
    /^(\s*(?:[-*]\s+)?(?:For\s+)?[xyz]\s*=\s*-?\d+\s*:\s*)(.+)$/i,
  );
  if (verifyLabel) {
    const expr = verifyLabel[2].replace(/\s*[✓✔✅]\s*$/u, "").trim();
    if (isMathLike(expr) || looksLikeBareEquation(expr)) {
      const mark = verifyLabel[2].match(/[✓✔✅]\s*$/u)?.[0] ?? "";
      return `${verifyLabel[1]}${wrapMath(expr)}${mark ? ` ${mark.trim()}` : ""}`;
    }
  }

  const trimmed = out.trim();
  if (looksLikeBareEquation(trimmed) && !trimmed.includes("$") && !/^[-*]\s/.test(trimmed)) {
    return out.replace(trimmed, wrapMath(trimmed));
  }

  out = out.replace(MATH_IN_PARENS_RE, (full, inner: string) => {
    if (!isMathLike(String(inner))) return full;
    return wrapMath(String(inner));
  });

  return out.replace(/^(\s*)\$\-\s*(.+?)\s*\$$/, "$1- $2");
}

export function normalizeImplicitMathInProse(text: string): string {
  return text.split("\n").map(normalizeMathLine).join("\n");
}

export function normalizeImplicitMath(content: string): string {
  const chunks: string[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = FENCE_RE.exec(content)) !== null) {
    if (match.index > last) {
      chunks.push(normalizeImplicitMathInProse(content.slice(last, match.index)));
    }
    chunks.push(match[0]);
    last = match.index + match[0].length;
  }
  chunks.push(normalizeImplicitMathInProse(content.slice(last)));
  return chunks.join("");
}
