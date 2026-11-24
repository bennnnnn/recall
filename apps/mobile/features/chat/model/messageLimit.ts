/**
 * The longest message a turn takes, in characters (apps/api/app/models/schemas/chats.py
 * MESSAGE_MAX_CHARS). The composer says so and holds Send back, rather than sending a
 * draft the API would refuse.
 */
export const MESSAGE_MAX_CHARS = 32_000;

/** One code point written as two UTF-16 units (an emoji, a rare CJK character). */
const SURROGATE_PAIR = /[\uD800-\uDBFF][\uDC00-\uDFFF]/g;

/**
 * The characters of the draft as it is sent (trimmed), counted as the API counts them: by
 * code point, so an emoji is one. `.length` counts it as two.
 */
export function messageChars(draft: string): number {
  const sent = draft.trim();
  // Never more code points than UTF-16 units: a draft this short is under the limit either way.
  if (sent.length <= MESSAGE_MAX_CHARS) return sent.length;
  return sent.length - (sent.match(SURROGATE_PAIR)?.length ?? 0);
}

export function messageTooLong(draft: string): boolean {
  return messageChars(draft) > MESSAGE_MAX_CHARS;
}
