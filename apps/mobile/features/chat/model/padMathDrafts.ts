/**
 * Drafts whose maths the math keyboard wrote, by their text, the least recently seen first.
 * Only these come back drawn as maths (`useMathKeyboardInsert`), and the saved drafts keep the
 * mark (`composerDraftFile`): "The price is $5" typed on the phone's keyboard was never maths,
 * and stays text.
 */
const padMathTexts = new Set<string>();
/** Enough for every kept draft and the steps that led to it. */
const MAX_PAD_MATH_TEXTS = 200;

/** The math keyboard wrote `text`'s maths (its preview is on). */
export function notePadMathDraft(text: string): void {
  padMathTexts.delete(text);
  padMathTexts.add(text);
  for (const oldest of padMathTexts) {
    if (padMathTexts.size <= MAX_PAD_MATH_TEXTS) break;
    padMathTexts.delete(oldest);
  }
}

/** Whether a draft brought back shows its maths drawn. */
export function isPadMathDraft(text: string): boolean {
  return padMathTexts.has(text);
}

/** Sign-out, with the saved drafts. */
export function forgetPadMathDrafts(): void {
  padMathTexts.clear();
}
