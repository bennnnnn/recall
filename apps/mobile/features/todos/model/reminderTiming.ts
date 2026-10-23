/** Pure reminder scheduling math — shared by local notifications and settings. */

export const REMINDER_LEAD_OPTIONS = [5, 10, 15, 30, 60] as const;
export type ReminderLeadMinutes = (typeof REMINDER_LEAD_OPTIONS)[number];

export const DEFAULT_REMINDER_LEAD_MINUTES: ReminderLeadMinutes = 10;

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

/** Clock time the alert is aimed at: due time minus the Settings lead. */
export function remindAtDate(dueAt: Date, leadMinutes: number): Date {
  return new Date(dueAt.getTime() - leadMsFromMinutes(normalizeReminderLeadMinutes(leadMinutes)));
}

/**
 * When to fire a local notification (null if due is past or invalid): the lead time before
 * it is due. A reminder already inside its lead window ("remind me in 3 minutes", lead 10)
 * fires when it is due, not the moment it is saved (twin: services/reminder_timing.py).
 */
export function reminderNotifyDate(
  dueAt: Date,
  now = new Date(),
  leadMs = leadMsFromMinutes(DEFAULT_REMINDER_LEAD_MINUTES),
): Date | null {
  const dueMs = dueAt.getTime();
  if (Number.isNaN(dueMs) || dueMs <= now.getTime()) return null;

  const notifyMs = dueMs - leadMs;
  return new Date(notifyMs <= now.getTime() ? dueMs : notifyMs);
}
