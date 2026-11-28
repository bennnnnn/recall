/** Strip server-side ```reminder fences from live chat (DB already strips on persist). */

import { stripLangFence } from "@/lib/fence/scan";

// The fence's language is exactly "reminder" (a stored ```reminder_proposal card is a retired
// fence, dropped in lib/markdown/assistantMessageContent.ts).
export function stripReminderFences(content: string): string {
  return stripLangFence(content, "reminder")
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd();
}
