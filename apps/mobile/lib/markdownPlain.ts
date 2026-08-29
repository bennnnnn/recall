/** Strip markdown to plain text for copy and TTS (do not import printDocument). */

import { stripClosedLangFence } from "@/lib/mdFenceScan";

const SERVER_FENCE_LANGS = ["answer", "geometry", "graph", "sources", "places"] as const;

function stripServerFences(text: string): string {
  let out = text;
  for (const lang of SERVER_FENCE_LANGS) {
    out = stripClosedLangFence(out, lang);
  }
  return out;
}

function fenceBodiesToPlain(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i] ?? "";
    const open = line.match(/^```([\w-]*)\s*$/);
    if (open) {
      i += 1;
      const body: string[] = [];
      while (i < lines.length && !/^```\s*$/.test(lines[i] ?? "")) {
        body.push(lines[i] ?? "");
        i += 1;
      }
      if (i < lines.length) i += 1;
      out.push(body.join("\n").trim());
      continue;
    }
    out.push(line);
    i += 1;
  }
  return out.join("\n");
}

function pipeTablesToPlain(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i] ?? "";
    if (looksLikePipeRow(line)) {
      const rows: string[] = [];
      while (i < lines.length && looksLikePipeRow(lines[i] ?? "")) {
        const cells = (lines[i] ?? "")
          .split("|")
          .map((c) => c.trim())
          .filter(Boolean);
        if (!cells.every((c) => /^:?-+:?$/.test(c))) {
          rows.push(cells.join(" — "));
        }
        i += 1;
      }
      out.push(rows.join("\n"));
      continue;
    }
    out.push(line);
    i += 1;
  }
  return out.join("\n");
}

function looksLikePipeRow(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.indexOf("|", 1) >= 0;
}

function mathToSpoken(text: string): string {
  return text
    .replace(/\$\$([\s\S]+?)\$\$/g, "$1")
    .replace(/\$([^$\n]+)\$/g, "$1")
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "$1 over $2")
    .replace(/\\sqrt\{([^}]+)\}/g, "sqrt $1")
    .replace(/\\times/g, " times ")
    .replace(/\\cdot/g, " dot ")
    .replace(/\\pm/g, " plus or minus ")
    .replace(/[{}]/g, "")
    .replace(/\^(\d+)/g, "^$1");
}

export function markdownToPlainText(markdown: string): string {
  let text = stripServerFences(markdown);
  text = fenceBodiesToPlain(text);
  text = pipeTablesToPlain(text);
  text = mathToSpoken(text);
  text = text.replace(/!\[[^\]]*\]\([^)]+\)/g, " ");
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");
  text = text.replace(/^#{1,6}\s+/gm, "");
  text = text.replace(/^>\s?/gm, "");
  text = text.replace(/^\s*[-*+]\s+/gm, "• ");
  text = text.replace(/^\s*\d+\.\s+/gm, "");
  text = text.replace(/(\*\*|__|\*|_|`|~~)/g, "");
  text = text.replace(/\n{3,}/g, "\n\n");
  return text.trim();
}
