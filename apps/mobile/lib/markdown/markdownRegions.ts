/**
 * Copy fenced regions byte for byte while rewriting the prose between them.
 * The API's twin is apps/api/app/modules/chat/markdown_regions.py; the
 * presentation passes on both sides walk a reply the same way.
 */

import { scanDisplayLine, type DisplayCloser } from "@/lib/markdown/displayDollars";
import { closesFence, readFenceMarker, type OpenFence } from "@/lib/fence/scan";

/** Restaurant price tiers, ($) to ($$$$), are not maths. */
export const PRICE_TIER = /\(\s*\$+\s*\)/;

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
  let open: OpenFence | null = null;
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
      if (marker && closesFence(marker, open)) {
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

/**
 * Which lines belong to a display formula left open across lines. A `$$` or
 * `\[` that a line leaves open makes every line up to its closer one formula,
 * which the phone draws as one maths block: none of them is a prose line to
 * lay out. Dollars are read as every reader reads them (`displayDollars.ts`):
 * inline code, price tiers and a `$$` that opens nothing hold no maths.
 */
export function displayMathLines(lines: string[]): boolean[] {
  let closer: DisplayCloser = null;
  return lines.map((line) => {
    // A list item or table row that ends a formula left open is no line of it.
    let dropped = false;
    const after = scanDisplayLine(line, closer, true, (kind) => {
      if (kind === "drop") dropped = true;
    });
    const kept = (closer != null && !dropped) || after != null;
    closer = after;
    return kept;
  });
}
