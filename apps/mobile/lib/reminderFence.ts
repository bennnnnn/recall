/** Strip server-side ```reminder fences from live chat (DB already strips on persist). */

const REMINDER_FENCE_RE = /```reminder\s*\n([\s\S]*?)```/gi;

export function stripReminderFences(content: string): string {
  return content
    .replace(REMINDER_FENCE_RE, "")
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd();
}

export function hasReminderFence(content: string): boolean {
  REMINDER_FENCE_RE.lastIndex = 0;
  return REMINDER_FENCE_RE.test(content);
}
