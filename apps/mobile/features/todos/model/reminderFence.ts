/** Strip server-side ```reminder fences from live chat (DB already strips on persist). */

import { stripClosedLangFence, stripUnclosedLangTail } from "@/lib/mdFenceScan";

// The fence's language is exactly "reminder": a ```reminder_proposal card is drawn, not stripped.
export function stripReminderFences(content: string): string {
  return stripUnclosedLangTail(stripClosedLangFence(content, "reminder"), "reminder")
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd();
}
