/** How a laid-out line ends: its note and its hard break (twin: calculation_layout_tail.py). */

/**
 * The laid-out rows of a line, then whatever followed the maths.
 *
 * "$h = …, k = …$ — Vertex of a parabola": the note names the first row, not a
 * line of its own. The line's hard break ("…$  ") still ends it, or the next
 * line runs on.
 */
export function finishInline(parts: string[], tail: string): string {
  const note = tail.trim();
  const last = parts.length > 0 ? parts[parts.length - 1] : "";
  if (note.startsWith("— ") && last.includes("\n")) {
    const cut = last.indexOf("\n");
    parts[parts.length - 1] =
      `${last.slice(0, cut).trimEnd()} ${note}  \n${last.slice(cut + 1)}`;
  } else if (note) {
    parts.push(parts.length > 0 ? tail.trimStart() : tail);
  }
  return keepHardBreak(tail, parts.join("\n"));
}

/** `laid` ends with `original`'s hard break, if it had one. */
export function keepHardBreak(original: string, laid: string): string {
  return original.endsWith("  ") ? `${laid.trimEnd()}  ` : laid;
}
