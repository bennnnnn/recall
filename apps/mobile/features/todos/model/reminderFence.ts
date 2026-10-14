/** Strip server-side ```reminder fences from live chat (DB already strips on persist). */

// Not ```reminder_proposal: that card is drawn, not stripped.
const REMINDER_FENCE_RE = /```reminder(?!_)\s*\n([\s\S]*?)```/gi;

export function stripReminderFences(content: string): string {
  return content
    .replace(REMINDER_FENCE_RE, "")
    .replace(/```reminder(?!_)[\s\S]*$/i, "")
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd();
}

export function hasReminderFence(content: string): boolean {
  REMINDER_FENCE_RE.lastIndex = 0;
  return REMINDER_FENCE_RE.test(content);
}
