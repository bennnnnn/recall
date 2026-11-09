/**
 * The quota nudge's per-day dismissal, kept in memory: it resets when the app restarts,
 * acceptable for a conversion nudge (it shows again once in the next session that day).
 * Apart from the hook so sign-out can clear it without importing the auth stack.
 */
import { utcDayKey } from "@/lib/datetime/dayKey";

let dismissedDate: string | null = null;

function today(): string {
  // The server's UTC day: a local date would dismiss the nudge across a midnight the
  // server has not crossed yet.
  return utcDayKey(new Date());
}

export function dismissQuotaNudgeToday(): void {
  dismissedDate = today();
}

export function quotaNudgeDismissedToday(): boolean {
  return dismissedDate === today();
}

/** Sign-out: the next account sees the nudge on its own terms. */
export function resetQuotaNudgeDismissal(): void {
  dismissedDate = null;
}
