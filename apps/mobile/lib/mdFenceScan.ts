/** Linear markdown-fence scan — no nested regex on assistant text. */

export function isFenceCloser(line: string): boolean {
  const stripped = line.trim();
  return stripped.length >= 3 && stripped === "`".repeat(stripped.length);
}

export function nextFenceMarkerLine(
  text: string,
  fromIndex: number,
): { start: number; after: number; stripped: string } | null {
  let index = fromIndex;
  while (index < text.length) {
    const newline = text.indexOf("\n", index);
    const end = newline < 0 ? text.length : newline;
    const line = text.slice(index, end);
    const stripped = line.trim();
    if (stripped.startsWith("```")) {
      return { start: index, after: newline < 0 ? text.length : newline + 1, stripped };
    }
    if (newline < 0) return null;
    index = newline + 1;
  }
  return null;
}

function findLangOpener(text: string, lang: string, start = 0): number | null {
  const needle = "```" + lang.toLowerCase();
  const lower = text.toLowerCase();
  let index = start;
  const tagLen = lang.length;
  while (true) {
    const pos = lower.indexOf(needle, index);
    if (pos < 0) return null;
    if (pos === 0 || text[pos - 1] === "\n") {
      const after = pos + 3 + tagLen;
      if (after >= text.length || " \t\r\n".includes(text[after] ?? "")) {
        return pos;
      }
    }
    index = pos + 1;
  }
}

export function collectClosedFenceBodies(text: string, lang: string): string[] {
  const bodies: string[] = [];
  mapClosedLangFence(text, lang, (body) => {
    bodies.push(body);
    return `\`\`\`${lang}\n${body}\`\`\``;
  });
  return bodies;
}

export function mapClosedLangFence(
  text: string,
  lang: string,
  replace: (body: string) => string,
): string {
  const pieces: string[] = [];
  let cursor = 0;
  let index = 0;
  while (true) {
    const opener = findLangOpener(text, lang, index);
    if (opener == null) {
      pieces.push(text.slice(cursor));
      break;
    }
    const newline = text.indexOf("\n", opener);
    if (newline < 0) {
      pieces.push(text.slice(cursor));
      break;
    }
    const marker = nextFenceMarkerLine(text, newline + 1);
    if (marker == null || !isFenceCloser(marker.stripped)) {
      index = newline + 1;
      continue;
    }
    pieces.push(text.slice(cursor, opener));
    pieces.push(replace(text.slice(newline + 1, marker.start)));
    cursor = marker.after;
    index = marker.after;
  }
  return pieces.join("");
}

export function stripClosedLangFence(text: string, lang: string): string {
  return mapClosedLangFence(text, lang, () => "");
}

/** Closed fences whose opener is bare ``` (no language tag). */
export function mapUnlabeledClosedFences(
  text: string,
  replace: (body: string, original: string) => string,
): string {
  const pieces: string[] = [];
  let index = 0;
  while (true) {
    const marker = nextFenceMarkerLine(text, index);
    if (marker == null) {
      pieces.push(text.slice(index));
      break;
    }
    const lang = marker.stripped.replace(/^`+/, "").trim();
    if (lang) {
      pieces.push(text.slice(index, marker.after));
      index = marker.after;
      continue;
    }
    const closer = nextFenceMarkerLine(text, marker.after);
    if (closer == null || !isFenceCloser(closer.stripped)) {
      pieces.push(text.slice(index, marker.after));
      index = marker.after;
      continue;
    }
    const body = text.slice(marker.after, closer.start);
    const original = text.slice(marker.start, closer.after);
    pieces.push(text.slice(index, marker.start));
    pieces.push(replace(body, original));
    index = closer.after;
  }
  return pieces.join("");
}
