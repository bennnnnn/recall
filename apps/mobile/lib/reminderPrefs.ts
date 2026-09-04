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
let pendingPreference: Promise<void> = Promise.resolve();

/** Keep startup migrations and writes ahead of signout/new-account cleanup. */
function withPreference<T>(operation: () => Promise<T>): Promise<T> {
  const result = pendingPreference.then(operation);
  pendingPreference = result.then(() => {}, () => {});
  return result;
}

function filePath(): string | null {
  return prefFilePath(FILE_NAME);
}

export function getReminderLeadMinutes(): Promise<ReminderLeadMinutes> {
  return withPreference(async () => {
    if (cachedLeadMinutes !== null) return cachedLeadMinutes;
    const fromFile = await readPrefFile(filePath());
    if (fromFile !== null) {
      cachedLeadMinutes = normalizeReminderLeadMinutes(Number.parseInt(fromFile, 10));
      return cachedLeadMinutes;
    }
    const legacy = await readLegacySecureStore(LEGACY_KEY);
    cachedLeadMinutes = normalizeReminderLeadMinutes(legacy ? Number.parseInt(legacy, 10) : undefined);
    if (legacy) await writePrefFile(filePath(), String(cachedLeadMinutes));
    return cachedLeadMinutes;
  });
}

export function setReminderLeadMinutes(minutes: ReminderLeadMinutes): Promise<void> {
  return withPreference(async () => {
    cachedLeadMinutes = minutes;
    await writePrefFile(filePath(), String(minutes));
  });
}

/** Align local scheduling prefs with the server profile (no API call). */
export function syncReminderLeadFromServer(minutes: unknown): Promise<ReminderLeadMinutes> {
  return withPreference(async () => {
    const normalized = normalizeReminderLeadMinutes(minutes);
    cachedLeadMinutes = normalized;
    await writePrefFile(filePath(), String(normalized));
    return normalized;
  });
}

export async function getReminderLeadMs(): Promise<number> {
  const minutes = await getReminderLeadMinutes();
  return leadMsFromMinutes(minutes);
}

export function clearReminderLeadPrefs(): Promise<void> {
  return withPreference(async () => {
    cachedLeadMinutes = null;
    await deletePrefFile(filePath());
    await deleteLegacySecureStore(LEGACY_KEY);
  });
}

/** Test helper — reset in-memory cache between cases. */
export function resetReminderLeadCache(): void {
  cachedLeadMinutes = null;
}
