/**
 * The reminder lead the Settings and to-do editor offer and show. When a reminder goes out is
 * the server's (each to-do's `notify_at`): the phone never works it out.
 */

export const REMINDER_LEAD_OPTIONS = [5, 10, 15, 30, 60] as const;
type ReminderLeadMinutes = (typeof REMINDER_LEAD_OPTIONS)[number];

export const DEFAULT_REMINDER_LEAD_MINUTES: ReminderLeadMinutes = 10;

function leadMsFromMinutes(minutes: number): number {
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

/** The editor's "Remind at": due time minus the Settings lead (the server's notify_at also
 * waits out quiet hours). */
export function remindAtDate(dueAt: Date, leadMinutes: number): Date {
  return new Date(dueAt.getTime() - leadMsFromMinutes(normalizeReminderLeadMinutes(leadMinutes)));
}
