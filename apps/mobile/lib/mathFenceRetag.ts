const LATEX_CMD_RE =
  /\\(?:pm|mp|sqrt|frac|text|mathrm|times|cdot|leq|geq|neq|infty|alpha|beta|gamma|theta|begin|left|right)\b/;

function looksLikeAlgebraLine(line: string): boolean {
  if (!line || line.length > 120) return false;
  if (/^(def |class |import |function |const |let |var |if |for |while )/i.test(line)) {
    return false;
  }
  if (/[;{}]|console\.|print\(|=>/.test(line)) return false;
  if (/^[a-zA-Z]\^[\d{]/.test(line)) return true;
  if (/=/.test(line) && /[a-zA-Z]\^/.test(line)) return true;
  if (/=/.test(line) && /^[\da-zA-Z+\-*/^=()\s.²³√±]+$/.test(line)) return true;
  return false;
}

/** Plain ``` or ```math body that should render as math, not a code block. */
export function looksLikeMathFenceBody(content: string): boolean {
  const s = content.trim();
  if (!s || s.length > 400) return false;
  if (s.startsWith("{")) return false;

  const lines = s.split("\n").filter((line) => line.trim());
  if (lines.length > 4) return false;

  if (LATEX_CMD_RE.test(s)) return true;
  if (/\\text\{/.test(s)) return true;

  if (lines.every((line) => looksLikeAlgebraLine(line.trim()))) {
    return lines.some((line) => /=/.test(line));
  }
  return false;
}

/** Model often emits ```latex — detect and reroute at render time. */
export function looksLikeLatexFence(content: string): boolean {
  return looksLikeMathFenceBody(content);
}

/** Rewrite model math fences before markdown parse (latex/plain → math only). */
export function retagMathAndDiagramFences(content: string): string {
  let out = content;

  out = out.replace(
    /```(?:latex|tex)\s*\n([\s\S]*?)```/gi,
    (_m, body: string) => `\`\`\`math\n${body.trim()}\n\`\`\``,
  );

  out = out.replace(/```\s*\n([\s\S]*?)```/g, (full, body: string) => {
    const trimmed = body.trim();
    if (looksLikeMathFenceBody(trimmed)) {
      return `\`\`\`math\n${trimmed}\n\`\`\``;
    }
    return full;
  });

  return out;
}
