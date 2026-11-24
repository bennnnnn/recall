/**
 * Where a dictation's words go in the composer's draft: at the caret where the take began,
 * between the text before it and the text after it, which the take never changes. With no
 * caret (the field was not being edited) the words follow the draft, as they always did.
 */

export type TextCaret = { start: number; end: number };

export type DictationAnchor = {
  /** The draft when the take began: what a take that heard nothing leaves. */
  original: string;
  before: string;
  after: string;
};

/** Split the draft at the caret; a selection keeps its text and the words go after it. */
export function dictationAnchor(draft: string, caret: TextCaret | null | undefined): DictationAnchor {
  const valid =
    caret != null &&
    Number.isInteger(caret.start) &&
    Number.isInteger(caret.end) &&
    caret.start >= 0 &&
    caret.end >= caret.start &&
    caret.end <= draft.length;
  if (!valid) return { original: draft, before: draft.trim(), after: "" };
  return { original: draft, before: draft.slice(0, caret.end), after: draft.slice(caret.end) };
}

// Text after the words that needs no space before it.
const CLOSES = /^[\s.,!?;:)\]}…»”’、。，！？]/u;

/** The draft with `words` at the anchor, a space on each side where the text needs one. */
export function draftWithDictation(anchor: DictationAnchor, words: string): string {
  const spoken = words.trim();
  if (!spoken) return anchor.original;
  const { before, after } = anchor;
  const lead = before && !/\s$/u.test(before) ? " " : "";
  const trail = after && !CLOSES.test(after) ? " " : "";
  return `${before}${lead}${spoken}${trail}${after}`;
}

/** Words that arrive after the draft moved on without the take: they follow whatever is there. */
export function appendDictation(draft: string, words: string): string {
  const spoken = words.trim();
  if (!spoken) return draft;
  return draft.trim() ? `${draft.trim()} ${spoken}` : spoken;
}
