import * as SecureStore from "expo-secure-store";

const KEY_PREFIX = "reminder-seen-";

function storageKey(userId: string): string {
  return `${KEY_PREFIX}${userId}`;
}

export async function loadSeenReminderIds(userId: string): Promise<Set<string>> {
  try {
    const raw = await SecureStore.getItemAsync(storageKey(userId));
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((id): id is string => typeof id === "string"));
  } catch {
    return new Set();
  }
}

export async function saveSeenReminderIds(userId: string, ids: Set<string>): Promise<void> {
  await SecureStore.setItemAsync(storageKey(userId), JSON.stringify([...ids]));
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
  await SecureStore.deleteItemAsync(storageKey(userId));
}
