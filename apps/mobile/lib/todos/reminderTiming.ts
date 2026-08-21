/** Pure reminder scheduling math — shared by local notifications and settings. */

export const REMINDER_LEAD_OPTIONS = [5, 10, 15, 30, 60] as const;
export type ReminderLeadMinutes = (typeof REMINDER_LEAD_OPTIONS)[number];

export const DEFAULT_REMINDER_LEAD_MINUTES: ReminderLeadMinutes = 10;
export const MAX_REMINDER_LEAD_MINUTES: ReminderLeadMinutes = 60;

/** When due is sooner than the lead window, fire almost immediately. */
export const IMMINENT_NOTIFY_DELAY_MS = 2_000;

export function leadMsFromMinutes(minutes: number): number {
  return minutes * 60 * 1000;
}

export function normalizeReminderLeadMinutes(raw: unknown): ReminderLeadMinutes {
  const parsed =
    typeof raw === "number" ? raw : Number.parseInt(String(raw ?? ""), 10);
  if (REMINDER_LEAD_OPTIONS.includes(parsed as ReminderLeadMinutes)) {
    return parsed as ReminderLeadMinutes;
  }
  return DEFAULT_REMINDER_LEAD_MINUTES;
}

/**
 * When to fire a local notification (null if due is past or invalid).
 * If the lead window already started, schedules ~2s from `now`.
 */
export function reminderNotifyDate(
  dueAt: Date,
  now = new Date(),
  leadMs = leadMsFromMinutes(DEFAULT_REMINDER_LEAD_MINUTES),
): Date | null {
  const dueMs = dueAt.getTime();
  if (Number.isNaN(dueMs) || dueMs <= now.getTime()) return null;

  const notifyMs = dueMs - leadMs;
  if (notifyMs <= now.getTime()) {
    return new Date(now.getTime() + IMMINENT_NOTIFY_DELAY_MS);
  }
  return new Date(notifyMs);
}

/** True when a push/local alert should fire for this due time and lead preference. */
export function isWithinReminderLeadWindow(
  dueAt: Date,
  now: Date,
  leadMinutes: number,
): boolean {
  const dueMs = dueAt.getTime();
  if (Number.isNaN(dueMs)) return false;
  if (dueMs < now.getTime()) return true;
  return dueMs <= now.getTime() + leadMsFromMinutes(leadMinutes);
}
