/**
 * Copy fenced regions byte for byte while rewriting the prose between them.
 * The API's twin is apps/api/app/modules/chat/markdown_regions.py; the
 * presentation passes on both sides walk a reply the same way.
 */

import { readFenceMarker } from "@/lib/mdFenceScan";

/**
 * Rewrite prose, and replace a closed fence when `rewriteFence` returns text.
 * `rewriteFence` receives the opener line, the body and the closer line; null
 * keeps that fence byte for byte. An unclosed fence stays raw.
 */
export function rewriteFenced(
  text: string,
  rewriteProse: (prose: string) => string,
  rewriteFence: (opener: string, body: string, closer: string) => string | null,
): string {
  if (!text) return rewriteProse(text);
  const out: string[] = [];
  let prose: string[] = [];
  let open: { char: "`" | "~"; len: number } | null = null;
  let opener = "";
  let body: string[] = [];
  const flush = () => {
    if (prose.length === 0) return;
    out.push(rewriteProse(prose.join("\n")));
    prose = [];
  };
  for (const line of text.split("\n")) {
    const marker = readFenceMarker(line);
    if (open) {
      if (marker && marker.char === open.char && marker.len >= open.len && marker.info === "") {
        const replacement = rewriteFence(opener, body.join("\n"), line);
        if (replacement == null) out.push(opener, ...body, line);
        else out.push(replacement);
        open = null;
        body = [];
      } else {
        body.push(line);
      }
      continue;
    }
    // ` ``` | ```java` is a broken table cell, not a fence opener.
    if (marker && !marker.info.includes("|")) {
      flush();
      open = { char: marker.char, len: marker.len };
      opener = line;
      continue;
    }
    prose.push(line);
  }
  flush();
  if (open) out.push(opener, ...body);
  return out.join("\n");
}

/** Indented code and blockquotes keep their source spacing. */
export function leaveProseLine(line: string): boolean {
  if (line.startsWith("    ") || line.startsWith("\t")) return true;
  return line.trimStart().startsWith(">");
}
