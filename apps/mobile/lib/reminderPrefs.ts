import * as SecureStore from "expo-secure-store";

import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  leadMsFromMinutes,
  normalizeReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
  type ReminderLeadMinutes,
} from "@/lib/reminderTiming";

export {
  DEFAULT_REMINDER_LEAD_MINUTES,
  REMINDER_LEAD_OPTIONS,
  type ReminderLeadMinutes,
};

const KEY = "reminder_lead_minutes";

let cachedLeadMinutes: ReminderLeadMinutes | null = null;

export async function getReminderLeadMinutes(): Promise<ReminderLeadMinutes> {
  if (cachedLeadMinutes !== null) return cachedLeadMinutes;
  try {
    const raw = await SecureStore.getItemAsync(KEY);
    cachedLeadMinutes = normalizeReminderLeadMinutes(
      raw ? Number.parseInt(raw, 10) : undefined,
    );
  } catch {
    cachedLeadMinutes = DEFAULT_REMINDER_LEAD_MINUTES;
  }
  return cachedLeadMinutes;
}

export async function setReminderLeadMinutes(minutes: ReminderLeadMinutes): Promise<void> {
  cachedLeadMinutes = minutes;
  await SecureStore.setItemAsync(KEY, String(minutes));
}

/** Align local scheduling prefs with the server profile (no API call). */
export async function syncReminderLeadFromServer(minutes: unknown): Promise<ReminderLeadMinutes> {
  const normalized = normalizeReminderLeadMinutes(minutes);
  cachedLeadMinutes = normalized;
  try {
    await SecureStore.setItemAsync(KEY, String(normalized));
  } catch {
    /* keep in-memory cache */
  }
  return normalized;
}

export async function getReminderLeadMs(): Promise<number> {
  const minutes = await getReminderLeadMinutes();
  return leadMsFromMinutes(minutes);
}
