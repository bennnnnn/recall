/** Matches simple "what time is it?" style questions (mirrors backend). */
const TIME_QUESTION =
  /^\s*(?:what(?:'s| is) the time(?:\s+now)?|what time is it(?:\s+now)?|tell me the (?:current )?time|current time\??|do you know the time\??|time(?:\s+please)?\??)\s*[.!?]*\s*$/i;

const TIME_FOLLOWUP =
  /^\s*(?:again|one more time|tell me again|refresh|update(?:\s+it)?)\s*[.!?]*\s*$/i;

const SCHEDULED_EVENT =
  /\b(meeting|appointment|flight|event|class|call|interview|game|train|bus)\b/i;

const DIGITAL_TIME_ONLY =
  /^\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM))?$/i;

const IANA_TIMEZONE_ONLY = /^[A-Za-z_+\-]+\/[A-Za-z_+\-]+(?:\/[A-Za-z_+\-]+)?$/;

export function isTimeQuestion(text: string): boolean {
  const cleaned = text.trim();
  if (!cleaned) return false;
  if (TIME_QUESTION.test(cleaned) || TIME_FOLLOWUP.test(cleaned)) {
    return !SCHEDULED_EVENT.test(cleaned);
  }
  return false;
}

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
  const match = markdown.match(/```[^\n]*\n([\s\S]*?)```/);
  if (!match) return "";
  const body = match[1].trim();
  return isIanaTimezoneOnly(body) ? body : "";
}

/** True when the assistant reply is mainly a time answer (clock widget should show). */
export function assistantReplyIsTimeAnswer(
  content: string,
  priorUserText: string | null,
): boolean {
  if (priorUserText && isTimeQuestion(priorUserText)) return true;
  if (/```\s*clock[\s\n]/i.test(content)) return true;
  const fence = content.match(/```[^\n]*\n([\s\S]*?)```/);
  if (fence && isClockFenceBody(fence[1])) return true;
  return false;
}
