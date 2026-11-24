/**
 * A long paste into the composer becomes a "Pasted text" attachment instead of text in the
 * field (features/attachments/model/pastedText.ts); a longer one than a paste may hold adds
 * nothing. A paste is read by its size, never its words: one change to the field that adds
 * more than PASTE_ATTACH_MIN_CHARS. Typing, autocorrect and dictation add a few at a time.
 */
import { PASTE_MAX_CHARS } from "@/features/attachments/model/pastedText";
import { charCount } from "@/lib/charCount";
import { nativeEditRange } from "@/lib/math/composerChange";
import type { TextSelection } from "@/lib/math/keyboardSymbols";

/** A paste of more than this many characters goes in as an attachment. */
export const PASTE_ATTACH_MIN_CHARS = 2_000;

export type ComposerPaste =
  /** Not a long paste: the change is the field's as it came. */
  | { kind: "text" }
  /** A long paste: `text` goes in as an attachment and the field holds `remaining`. */
  | { kind: "attach"; text: string; remaining: string }
  /** Longer than a paste may be: nothing is added and the field keeps what it had. */
  | { kind: "too_long" };

/** What `pasted`, put in at the caret of a field holding `remaining`, does to it. */
export function readPastedText(pasted: string, remaining: string): ComposerPaste {
  // Counted as the API counts (an emoji is one); `.length` is never less, so most edits stop here.
  if (pasted.length <= PASTE_ATTACH_MIN_CHARS) return { kind: "text" };
  const chars = charCount(pasted);
  if (chars <= PASTE_ATTACH_MIN_CHARS) return { kind: "text" };
  if (chars > PASTE_MAX_CHARS) return { kind: "too_long" };
  return { kind: "attach", text: pasted, remaining };
}

/**
 * The field's change from `previous` to `next`, read as a paste or not. A paste over a
 * selection replaces it, as it would in the field: the selection is gone from `remaining`.
 *
 * `selection` is the field's selection before the change. The paste went in there, so it
 * is cut out by it: matching the two texts from both ends alone would keep a character the
 * paste and the draft share at an edge as draft text ("Fix this." pasted over with a text
 * ending in "." would leave "." behind). A selection the change does not fit (one the
 * field had not reported yet) falls back to that match.
 */
export function readComposerChange(previous: string, next: string, selection?: TextSelection): ComposerPaste {
  const at = selection ? pasteAt(previous, next, selection) : null;
  if (at) return readPastedText(at.added, at.remaining);
  const range = nativeEditRange(previous, next);
  if (!range) return { kind: "text" };
  const remaining = previous.slice(0, range.at) + previous.slice(range.at + range.removed.length);
  return readPastedText(range.added, remaining);
}

/** What went in over `selection`, when `next` is `previous` with exactly that range replaced. */
function pasteAt(previous: string, next: string, { start, end }: TextSelection) {
  if (start < 0 || end < start || end > previous.length) return null;
  const length = next.length - (previous.length - (end - start));
  if (length <= 0) return null;
  const before = previous.slice(0, start);
  const after = previous.slice(end);
  if (!next.startsWith(before) || !next.endsWith(after)) return null;
  return { added: next.slice(start, start + length), remaining: before + after };
}
