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

/**
 * Rewrite model math fences before markdown parse (latex/plain → math only).
 *
 * Matches every fence (tagged or not) in a single pass, so an already-tagged
 * fence's own closing ``` is always consumed as part of ITS match, never
 * mistaken for the opener of a new bare fence — a bare-fence-only regex here
 * previously matched a tagged fence's closing ``` as an opener, silently
 * swallowing everything up to the next fence as a single bogus "math" block.
 */
export function retagMathAndDiagramFences(content: string): string {
  let out = content;

  out = out.replace(
    /```(?:latex|tex)\s*\n([\s\S]*?)```/gi,
    (_m, body: string) => `\`\`\`math\n${body.trim()}\n\`\`\``,
  );

  out = out.replace(/```([^\n]*)\n([\s\S]*?)```/g, (full, info: string, body: string) => {
    if (info.trim()) return full;
    const trimmed = body.trim();
    if (looksLikeMathFenceBody(trimmed)) {
      return `\`\`\`math\n${trimmed}\n\`\`\``;
    }
    return full;
  });

  return out;
}
