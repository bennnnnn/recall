/**
 * A long paste into the composer becomes a "Pasted text" attachment instead of text in the
 * field (features/attachments/model/pastedText.ts); a longer one than a paste may hold adds
 * nothing. A paste is read by its size, never its words: one change to the field that adds
 * more than PASTE_ATTACH_MIN_CHARS. Typing, autocorrect and dictation add a few at a time.
 */
import { PASTE_MAX_CHARS } from "@/features/attachments/model/pastedText";
import { nativeEditRange } from "@/lib/math/composerChange";

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
  if (pasted.length <= PASTE_ATTACH_MIN_CHARS) return { kind: "text" };
  if (pasted.length > PASTE_MAX_CHARS) return { kind: "too_long" };
  return { kind: "attach", text: pasted, remaining };
}

/**
 * The field's change from `previous` to `next`, read as a paste or not. A paste over a
 * selection replaces it, as it would in the field: the selection is gone from `remaining`.
 */
export function readComposerChange(previous: string, next: string): ComposerPaste {
  const range = nativeEditRange(previous, next);
  if (!range) return { kind: "text" };
  const remaining = previous.slice(0, range.at) + previous.slice(range.at + range.removed.length);
  return readPastedText(range.added, remaining);
}
