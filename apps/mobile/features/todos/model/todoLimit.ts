/**
 * The API keeps at most so many open to-dos for one account (apps/api modules/todos/limits.py
 * OPEN_TODOS_MAX). An add past it, or reopening a completed one, is refused with the code
 * `todo_limit`, and the person is told so in their language, not "Could not save".
 */
export const TODO_LIMIT_CODE = "todo_limit";

/** Whether a failed to-do change was refused for the account's open to-do cap. */
export function isTodoLimit(error: unknown): boolean {
  return Boolean(error && typeof error === "object" && (error as { code?: unknown }).code === TODO_LIMIT_CODE);
}

/** The message key for a failed to-do change: the cap's own, or the change's usual one. */
export function todoErrorKey(error: unknown, fallback: string): string {
  return isTodoLimit(error) ? "todos.error_limit" : fallback;
}
