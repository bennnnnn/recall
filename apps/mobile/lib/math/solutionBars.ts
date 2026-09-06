/**
 * Models often join two roots with `|` / `\mid` (programming OR). KaTeX
 * display mode draws that as a tall delimiter. Rewrite to "or" when the
 * bar sits between two `=` clauses. Leave absolute value `|x|` and
 * "such that" `{x \mid x>0}` alone.
 */

const MID_COMMANDS = [
  "\\bigm|",
  "\\Bigm|",
  "\\middle|",
  "\\Bigg|",
  "\\bigg|",
  "\\Big|",
  "\\big|",
  "\\mid",
  "\\vert",
];

function hasEquals(s: string): boolean {
  return s.includes("=");
}

function replaceAllCmd(latex: string, cmd: string): string {
  let out = "";
  let i = 0;
  const n = latex.length;
  while (i < n) {
    const at = latex.indexOf(cmd, i);
    if (at < 0) {
      out += latex.slice(i);
      break;
    }
    out += latex.slice(i, at);
    const left = out;
    const right = latex.slice(at + cmd.length);
    if (hasEquals(left) && hasEquals(right)) {
      out += " \\text{ or } ";
    } else {
      out += cmd;
    }
    i = at + cmd.length;
  }
  return out;
}

function isAbsOrDelimiter(latex: string, barAt: number): boolean {
  const before = latex.slice(Math.max(0, barAt - 6), barAt);
  return before.endsWith("\\left") || before.endsWith("\\right");
}

function replaceBareBars(latex: string): string {
  let out = "";
  let i = 0;
  const n = latex.length;
  while (i < n) {
    const ch = latex[i];
    if (ch !== "|") {
      out += ch;
      i += 1;
      continue;
    }
    if (latex[i - 1] === "\\") {
      out += ch;
      i += 1;
      continue;
    }
    if (isAbsOrDelimiter(latex, i)) {
      out += ch;
      i += 1;
      continue;
    }
    const left = out;
    const right = latex.slice(i + 1);
    if (hasEquals(left) && hasEquals(right)) {
      out += " \\text{ or } ";
    } else {
      out += "|";
    }
    i += 1;
  }
  return out;
}

/** Linear rewrite — no nested regex. */
export function rewriteSolutionSeparatorBars(latex: string): string {
  let s = latex;
  for (const cmd of MID_COMMANDS) {
    s = replaceAllCmd(s, cmd);
  }
  return replaceBareBars(s);
}

/** Turn `\\[ ... \\]` / `$$ ... $$` into `$...$` so user bubbles stay compact. */
export function displayMathToInline(text: string): string {
  let out = "";
  let i = 0;
  const n = text.length;
  while (i < n) {
    if (text.startsWith("$$", i)) {
      const close = text.indexOf("$$", i + 2);
      if (close < 0) {
        out += text.slice(i);
        break;
      }
      out += `$${text.slice(i + 2, close).trim()}$`;
      i = close + 2;
      continue;
    }
    if (text.startsWith("\\[", i)) {
      const close = text.indexOf("\\]", i + 2);
      if (close < 0) {
        out += text.slice(i);
        break;
      }
      out += `$${text.slice(i + 2, close).trim()}$`;
      i = close + 2;
      continue;
    }
    out += text[i];
    i += 1;
  }
  return out;
}
