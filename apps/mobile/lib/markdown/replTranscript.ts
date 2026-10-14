/**
 * A Python `>>>` transcript written as prose becomes a code block.
 *
 * Markdown reads `>>> two_sum([2, 7], 9)` as three nested quotes, so a reply
 * that shows a REPL session outside a fence draws stacked quote bars and runs
 * the call into its output. The transcript, up to the next blank line, is
 * wrapped in a ```python fence instead. The API does the same
 * (`apps/api/app/modules/chat/repl_transcript.py`).
 */

const PROMPT = /^[ \t]{0,3}>>>(?:[ \t]|$)/;
const FENCE = /^[ \t]{0,3}(`{3,}|~{3,})/;

export function fenceReplTranscripts(text: string): string {
  if (!text || !text.includes(">>>")) return text;
  const lines = text.split("\n");
  const out: string[] = [];
  let open: string | null = null;
  let index = 0;
  while (index < lines.length) {
    const line = lines[index]!;
    const fence = line.match(FENCE)?.[1];
    if (open !== null) {
      if (
        fence &&
        fence[0] === open[0] &&
        fence.length >= open.length &&
        !line.trim().slice(fence.length)
      ) {
        open = null;
      }
      out.push(line);
      index += 1;
      continue;
    }
    if (fence) {
      open = fence;
      out.push(line);
      index += 1;
      continue;
    }
    if (!PROMPT.test(line)) {
      out.push(line);
      index += 1;
      continue;
    }
    const block: string[] = [];
    while (index < lines.length && lines[index]!.trim()) {
      block.push(lines[index]!.trim());
      index += 1;
    }
    out.push("```python", ...block, "```");
  }
  return out.join("\n");
}
