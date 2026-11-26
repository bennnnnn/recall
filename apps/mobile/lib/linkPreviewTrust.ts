/**
 * Which links in a message may show a fetched preview card.
 *
 * A preview makes the server fetch the URL, path, query and all. A URL the
 * model wrote on its own can carry the user's memory or schedule to its host
 * when injected text (a web result, a PDF) told it to, so only links the user
 * wrote or the server's own search returned qualify. Every other link is a
 * plain card that fetches nothing (`components/LinkPreviewCard.tsx`).
 *
 * "The user wrote" is the words they typed: a stored message also holds what
 * the server put after them (an attached file's text, a paste, the words read off
 * a scanner photo), and a link there was written by whoever wrote the file or the
 * page. Counted as the user's, a document could have the reply end on a link that
 * carries the user's data and have it fetched without a tap (security review,
 * 2026-11-25), so `typedByUser` keeps only the typed words.
 */
import { SCANNER_CAMERA_PROMPTS } from "@/lib/scanner/subjects";

const URL_IN_TEXT = /https?:\/\/[^\s<>"'`]+/gi;
const TRAILING_PUNCTUATION = /[.,;:!?'"\]}>]+$/;

/** One spelling per URL: normalized by URL parsing, without its #fragment (never sent). */
export function linkPreviewKey(url: string): string | null {
  try {
    const parsed = new URL(url.trim());
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return null;
    parsed.hash = "";
    return parsed.href;
  } catch {
    return null;
  }
}

function count(text: string, char: string): number {
  return text.split(char).length - 1;
}

/** A closing ")" belongs to the URL only when the URL opened one (Wikipedia's "Foo_(bar)"). */
function trimUrlEnd(raw: string): string {
  let url = raw.replace(TRAILING_PUNCTUATION, "");
  while (url.endsWith(")") && count(url, "(") < count(url, ")")) {
    url = url.slice(0, -1).replace(TRAILING_PUNCTUATION, "");
  }
  return url;
}

// The lines the server writes for an attachment (apps/api prompt_safety.py
// _ATTACHMENT_MARKERS); everything from the first one on is the attachments' text.
const ATTACHMENT_MARKERS = ["[File:", "[Image:", "[File attached:", "[File ("];
// The line the turn's photo reader writes under a scan's caption (docs/fixtures/scanner_prompts.json).
export const SCAN_READING_PREFIX = "I read this as:";

/**
 * The words the user typed in a message: not its attachments' text (cut at the first marker
 * line, as the API's `text_before_attachment_markers` does) and not what a scanner photo was
 * read as. The reading opens the message, under the scan's caption or, in the bubble (whose
 * caption `stripScannerProtocolCaption` has already taken off), on its own, and runs to the
 * first blank line; the one rule reads both, so the bubble and the reply under it agree.
 */
function typedByUser(content: string): string {
  const lines = content.split("\n");
  const first = lines.findIndex((line) => ATTACHMENT_MARKERS.some((marker) => line.trimStart().startsWith(marker)));
  const typed = (first < 0 ? lines : lines.slice(0, first)).join("\n").trimStart();
  const prompt = Object.values(SCANNER_CAMERA_PROMPTS).find((caption) => typed.startsWith(caption)) ?? "";
  const after = typed.slice(prompt.length).trimStart();
  if (!after.startsWith(SCAN_READING_PREFIX)) return typed;
  const blank = after.search(/\n[ \t]*\n/);
  return blank < 0 ? prompt : `${prompt}${after.slice(blank)}`;
}

/** The previewable links: every URL the user typed, and the reply's search sources. */
export function previewableUrls(
  userTexts: readonly (string | null | undefined)[],
  sources: readonly { url: string }[] = [],
): ReadonlySet<string> {
  const keys = new Set<string>();
  for (const text of userTexts) {
    for (const match of typedByUser(text ?? "").match(URL_IN_TEXT) ?? []) {
      const key = linkPreviewKey(trimUrlEnd(match));
      if (key) keys.add(key);
    }
  }
  for (const source of sources) {
    const key = linkPreviewKey(source.url);
    if (key) keys.add(key);
  }
  return keys;
}
