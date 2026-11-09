/**
 * A calendar day as `YYYY-MM-DD`, which sorts and compares as text. Two days exist on the
 * phone: the user's own, and the server's quota day.
 */

/** The phone's calendar day in its own zone: "today" as the user lives it. */
export function localDayKey(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** The server's day: the daily allowance resets at UTC midnight (`/usage/today`). */
export function utcDayKey(date: Date): string {
  return date.toISOString().slice(0, 10);
}
