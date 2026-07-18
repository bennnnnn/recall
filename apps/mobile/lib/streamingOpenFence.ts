/**
 * Classify the unstable streaming tail when a fence / block-math delimiter
 * is still open. Callers render these as plain text so markdown-it (+ Prism)
 * does not re-tokenize a growing open fence every throttle tick.
 */

export type OpenStreamScan = {
  fenceOpen: boolean;
  dollarOpen: boolean;
  bracketDepth: number;
};

export type OpenStreamRegion =
  | { kind: "fence"; lang: string; body: string }
  | { kind: "math"; body: string }
  | { kind: "other"; text: string };

const OPEN_FENCE_RE = /^(```|~~~)([^\n]*)(?:\n([\s\S]*))?$/;

export function parseOpenFenceTail(liveRaw: string): { lang: string; body: string } | null {
  const match = OPEN_FENCE_RE.exec(liveRaw);
  if (!match) return null;
  return {
    lang: (match[2] ?? "").trim(),
    body: match[3] ?? "",
  };
}

export function parseOpenMathTail(liveRaw: string): string | null {
  if (liveRaw.startsWith("$$")) {
    const rest = liveRaw.slice(2);
    return rest.startsWith("\n") ? rest.slice(1) : rest;
  }
  if (liveRaw.startsWith("\\[")) {
    const rest = liveRaw.slice(2);
    return rest.startsWith("\n") ? rest.slice(1) : rest;
  }
  return null;
}

export function classifyOpenStreamTail(
  liveRaw: string,
  scan: OpenStreamScan | null | undefined,
): OpenStreamRegion {
  if (!liveRaw) return { kind: "other", text: "" };

  if (scan?.fenceOpen) {
    const fence = parseOpenFenceTail(liveRaw);
    if (fence) return { kind: "fence", lang: fence.lang, body: fence.body };
  }

  if (scan?.dollarOpen || (scan?.bracketDepth ?? 0) !== 0) {
    const body = parseOpenMathTail(liveRaw);
    if (body != null) return { kind: "math", body };
  }

  return { kind: "other", text: liveRaw };
}
