import {
  deleteLegacySecureStore,
  deletePrefFile,
  prefFilePath,
  readLegacySecureStore,
  readPrefFile,
  writePrefFile,
} from "@/lib/filePrefs";
import {
  DEFAULT_REMINDER_LEAD_MINUTES,
  leadMsFromMinutes,
  normalizeReminderLeadMinutes,
  REMINDER_LEAD_OPTIONS,
  type ReminderLeadMinutes,
} from "@/lib/todos/reminderTiming";

export {
  DEFAULT_REMINDER_LEAD_MINUTES,
  REMINDER_LEAD_OPTIONS,
  type ReminderLeadMinutes,
};

const LEGACY_KEY = "reminder_lead_minutes";
const FILE_NAME = "recall.reminder-lead-minutes.txt";

let cachedLeadMinutes: ReminderLeadMinutes | null = null;

function filePath(): string | null {
  return prefFilePath(FILE_NAME);
}

export async function getReminderLeadMinutes(): Promise<ReminderLeadMinutes> {
  if (cachedLeadMinutes !== null) return cachedLeadMinutes;
  const fromFile = await readPrefFile(filePath());
  if (fromFile !== null) {
    cachedLeadMinutes = normalizeReminderLeadMinutes(Number.parseInt(fromFile, 10));
    return cachedLeadMinutes;
  }

  const legacy = await readLegacySecureStore(LEGACY_KEY);
  cachedLeadMinutes = normalizeReminderLeadMinutes(
    legacy ? Number.parseInt(legacy, 10) : undefined,
  );
  if (legacy) {
    await writePrefFile(filePath(), String(cachedLeadMinutes));
  }
  return cachedLeadMinutes;
}

export async function setReminderLeadMinutes(minutes: ReminderLeadMinutes): Promise<void> {
  cachedLeadMinutes = minutes;
  await writePrefFile(filePath(), String(minutes));
}

/** Align local scheduling prefs with the server profile (no API call). */
export async function syncReminderLeadFromServer(minutes: unknown): Promise<ReminderLeadMinutes> {
  const normalized = normalizeReminderLeadMinutes(minutes);
  cachedLeadMinutes = normalized;
  await writePrefFile(filePath(), String(normalized));
  return normalized;
}

export async function getReminderLeadMs(): Promise<number> {
  const minutes = await getReminderLeadMinutes();
  return leadMsFromMinutes(minutes);
}

export async function clearReminderLeadPrefs(): Promise<void> {
  cachedLeadMinutes = null;
  await deletePrefFile(filePath());
  await deleteLegacySecureStore(LEGACY_KEY);
}

/** Test helper — reset in-memory cache between cases. */
export function resetReminderLeadCache(): void {
  cachedLeadMinutes = null;
}
