/**
 * Time answers as the reply carries them. The server decides what a time
 * question is (`is_time_question` in apps/api/app/services/time_context.py)
 * and answers a local one with an empty ```clock fence; the phone only reads
 * the reply, never the user's words.
 */

const DIGITAL_TIME_ONLY =
  /^\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM))?$/i;

const IANA_TIMEZONE_ONLY = /^[A-Za-z_+\-]+\/[A-Za-z_+\-]+(?:\/[A-Za-z_+\-]+)?$/;

/** A ```clock opener; `[ \t]` keeps "```\nclock speed…" from matching. */
const CLOCK_FENCE_OPEN = /```[ \t]*clock\s/i;

const FIRST_FENCE = /```[^\n]*\n([\s\S]*?)```/;

export function isDigitalTimeOnly(text: string): boolean {
  const t = text.trim().replace(/^\*\*|\*\*$/g, "").trim();
  return DIGITAL_TIME_ONLY.test(t);
}

export function isIanaTimezoneOnly(text: string): boolean {
  return IANA_TIMEZONE_ONLY.test(text.trim());
}

export function isClockFenceBody(text: string): boolean {
  const body = text.trim();
  if (!body) return true;
  return isDigitalTimeOnly(body) || isIanaTimezoneOnly(body);
}

/** Strip time-answer fences (static time, timezone, empty clock blocks). */
export function stripTimeAnswerFences(markdown: string): string {
  return markdown
    .replace(/```[^\n]*\n([\s\S]*?)```/g, (match, body: string) =>
      isClockFenceBody(body) ? "" : match,
    )
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function extractClockTimezone(markdown: string): string {
  const match = markdown.match(FIRST_FENCE);
  if (!match) return "";
  const body = match[1].trim();
  return isIanaTimezoneOnly(body) ? body : "";
}

/**
 * True when the reply is a time answer, so the live clock card shows: a
 * ```clock fence, or a first fence holding only a clock reading or a timezone.
 */
export function assistantReplyIsTimeAnswer(content: string): boolean {
  if (CLOCK_FENCE_OPEN.test(content)) return true;
  const fence = content.match(FIRST_FENCE);
  if (!fence) return false;
  return isDigitalTimeOnly(fence[1]) || isIanaTimezoneOnly(fence[1]);
}
