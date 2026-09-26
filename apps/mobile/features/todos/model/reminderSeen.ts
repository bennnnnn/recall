import {
  deleteLegacySecureStore,
  deletePrefFile,
  prefFilePath,
  readLegacySecureStore,
  readPrefFile,
  safePrefUserId,
  writePrefFile,
} from "@/lib/filePrefs";

const LEGACY_KEY_PREFIX = "reminder-seen-";

function legacyKey(userId: string): string {
  return `${LEGACY_KEY_PREFIX}${userId}`;
}

function filePath(userId: string): string | null {
  return prefFilePath(`recall.reminder-seen.${safePrefUserId(userId)}.json`);
}

function parseIds(raw: string): Set<string> {
  const parsed = JSON.parse(raw) as unknown;
  if (!Array.isArray(parsed)) return new Set();
  return new Set(parsed.filter((id): id is string => typeof id === "string"));
}

export async function loadSeenReminderIds(userId: string): Promise<Set<string>> {
  const fromFile = await readPrefFile(filePath(userId));
  if (fromFile !== null) {
    try {
      return parseIds(fromFile);
    } catch {
      return new Set();
    }
  }

  const legacy = await readLegacySecureStore(legacyKey(userId));
  if (!legacy) return new Set();
  try {
    const ids = parseIds(legacy);
    if (ids.size > 0) {
      await saveSeenReminderIds(userId, ids);
    }
    return ids;
  } catch {
    return new Set();
  }
}

export async function saveSeenReminderIds(userId: string, ids: Set<string>): Promise<void> {
  await writePrefFile(filePath(userId), JSON.stringify([...ids]));
}

/** Drop seen ids for todos that are gone or completed. */
export function pruneSeenReminderIds(seen: Set<string>, openTodoIds: Iterable<string>): Set<string> {
  const open = new Set(openTodoIds);
  return new Set([...seen].filter((id) => open.has(id)));
}

export async function markReminderIdsSeen(userId: string, ids: string[]): Promise<void> {
  if (ids.length === 0) return;
  const seen = await loadSeenReminderIds(userId);
  for (const id of ids) seen.add(id);
  await saveSeenReminderIds(userId, seen);
}

export async function clearSeenReminderIds(userId: string): Promise<void> {
  await deletePrefFile(filePath(userId));
  await deleteLegacySecureStore(legacyKey(userId));
}
