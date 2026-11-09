const CHAT_ROW_ACTIONS = ["share", "rename", "pin", "archive", "delete"] as const;

/** What a drawer row's long-press menu does to its chat, also offered to screen readers on the row. */
export type ChatRowAction = (typeof CHAT_ROW_ACTIONS)[number];

/** A screen reader's action name is one of these, not "activate" or a platform's own. */
export function isChatRowAction(name: string): name is ChatRowAction {
  return (CHAT_ROW_ACTIONS as readonly string[]).includes(name);
}
