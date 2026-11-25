/** One code point written as two UTF-16 units (an emoji, a rare CJK character). */
const SURROGATE_PAIR = /[\uD800-\uDBFF][\uDC00-\uDFFF]/g;

/**
 * Characters as the API counts them: by code point, so an emoji is one. `.length` counts it
 * as two. Never more than `.length`, so a text that short needs no count.
 */
export function charCount(text: string): number {
  return text.length - (text.match(SURROGATE_PAIR)?.length ?? 0);
}
