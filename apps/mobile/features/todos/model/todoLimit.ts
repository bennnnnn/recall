/**
 * The API keeps at most so many open to-dos for one account (apps/api modules/todos/limits.py
 * OPEN_TODOS_MAX). An add past it, or reopening a completed one, is refused with the code
 * `todo_limit`, and the person is told so in their language, not "Could not save".
 */
const TODO_LIMIT_CODE = "todo_limit";
/** An open to-do already has this title at this time, or as a date alone on this day
 * (apps/api modules/todos/crud.py `_duplicate`). It said "Could not update". */
const TODO_DUPLICATE_CODE = "todo_duplicate";

function codeOf(error: unknown): unknown {
  return error && typeof error === "object" ? (error as { code?: unknown }).code : undefined;
}

/** Whether a failed to-do change was refused for the account's open to-do cap. */
function isTodoLimit(error: unknown): boolean {
  return codeOf(error) === TODO_LIMIT_CODE;
}

/** The message key for a failed to-do change: the refusal's own, or the change's usual one. */
export function todoErrorKey(error: unknown, fallback: string): string {
  if (isTodoLimit(error)) return "todos.error_limit";
  return codeOf(error) === TODO_DUPLICATE_CODE ? "todos.error_duplicate" : fallback;
}
