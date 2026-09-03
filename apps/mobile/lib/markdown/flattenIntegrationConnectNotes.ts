/**
 * Calendar/Gmail "not connected" copy must stay plain markdown.
 * Models wrap it in `>` (quote card) or `> Tip:` / `> Note:` (callout card).
 */

const CALLOUT_LABELS = ["tip:", "note:", "warning:", "important:", "info:"];

export function isIntegrationConnectNote(text: string): boolean {
  const t = text.toLowerCase();
  const disconnected =
    t.includes("not connected") ||
    t.includes("isn't connected") ||
    t.includes("isnt connected");
  if (!disconnected) return false;
  const product =
    t.includes("calendar") || t.includes("gmail") || t.includes("inbox");
  if (!product) return false;
  return t.includes("settings") || t.includes("connect") || t.includes("link");
}

function stripBlockquotePrefix(line: string): string {
  let i = 0;
  while (i < line.length && (line[i] === " " || line[i] === "\t")) i += 1;
  if (line[i] !== ">") return line;
  i += 1;
  if (line[i] === " ") i += 1;
  return line.slice(i);
}

function stripLeadingCalloutChrome(body: string): string {
  let t = body.trim();
  if (t.startsWith("[!")) {
    const close = t.indexOf("]");
    if (close !== -1) t = t.slice(close + 1).trim();
  }
  const lower = t.toLowerCase();
  for (const label of CALLOUT_LABELS) {
    if (lower.startsWith(label)) {
      t = t.slice(label.length).trim();
      break;
    }
  }
  return t;
}

function flattenBlockquoteRuns(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let i = 0;
  let inFence = false;
  while (i < lines.length) {
    const line = lines[i] ?? "";
    const trimmed = line.trimStart();
    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      out.push(line);
      i += 1;
      continue;
    }
    if (inFence || !trimmed.startsWith(">")) {
      out.push(line);
      i += 1;
      continue;
    }
    const raw: string[] = [];
    const bodies: string[] = [];
    while (i < lines.length) {
      const cur = lines[i] ?? "";
      if (!cur.trimStart().startsWith(">")) break;
      raw.push(cur);
      bodies.push(stripLeadingCalloutChrome(stripBlockquotePrefix(cur)));
      i += 1;
    }
    if (isIntegrationConnectNote(bodies.join(" "))) {
      for (const body of bodies) {
        if (body) out.push(body);
      }
    } else {
      out.push(...raw);
    }
  }
  return out.join("\n");
}

function flattenConnectCalloutFences(content: string): string {
  const lines = content.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i] ?? "";
    const trimmed = line.trim();
    const isCalloutFence =
      trimmed.startsWith("```callout-") || trimmed === "```callout";
    if (!isCalloutFence) {
      out.push(line);
      i += 1;
      continue;
    }
    const raw = [line];
    const body: string[] = [];
    i += 1;
    while (i < lines.length) {
      const cur = lines[i] ?? "";
      raw.push(cur);
      i += 1;
      if (cur.trim().startsWith("```")) break;
      body.push(cur);
    }
    if (isIntegrationConnectNote(body.join(" "))) {
      for (const row of body) {
        const cleaned = stripLeadingCalloutChrome(row);
        if (cleaned) out.push(cleaned);
      }
    } else {
      out.push(...raw);
    }
  }
  return out.join("\n");
}

/** Drop quote/callout wrapping around Calendar/Gmail connect notes. */
export function flattenIntegrationConnectNotes(content: string): string {
  return flattenConnectCalloutFences(flattenBlockquoteRuns(content));
}
