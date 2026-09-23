/** Unicode-aware matching preserves the original offsets and never matches inside a word. */
export function wholeWordIndex(sentence: string, target: string, from = 0): number {
  const word = target.trim();
  if (!word) return -1;
  const pattern = new RegExp(word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "giu");
  pattern.lastIndex = from;
  const letters = /[\p{L}\p{N}\p{M}_]/u;
  for (let match = pattern.exec(sentence); match; match = pattern.exec(sentence)) {
    const before = [...sentence.slice(0, match.index)].at(-1) ?? "";
    const after = [...sentence.slice(match.index + match[0].length)][0] ?? "";
    if (!letters.test(before) && !letters.test(after)) return match.index;
  }
  return -1;
}
