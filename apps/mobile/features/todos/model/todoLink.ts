/**
 * ```todo_link: a reply to a message that asked chat to add or change a to-do, in any
 * language. Chat and live talk only read to-dos; reminders are added and changed in the
 * To-do screen, which the reply offers as a button (the server writes the fence). The
 * fence has no body.
 */
import { collectClosedFenceBodies, stripLangFence } from "@/lib/fence/scan";

const LANG = "todo_link";

/** The reply ends on an Open To-do button. */
export function hasTodoLink(content: string): boolean {
  return content.includes("```todo_link") && collectClosedFenceBodies(content, LANG).length > 0;
}

/** The reply's text without the fence, settled or still streaming. */
export function stripTodoLinkFences(content: string): string {
  if (!content.includes("```todo_link")) return content;
  return stripLangFence(content, LANG)
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
