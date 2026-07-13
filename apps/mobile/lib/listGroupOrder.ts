/**
 * Persist custom list (todo topic) order. Not a secret — use the filesystem,
 * not SecureStore (Keychain). A linker-signed / entitlement-less simulator
 * build rejects Keychain writes with errSecMissingEntitlement (-34018).
 */

import {
  documentDirectory,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";
import * as SecureStore from "expo-secure-store";

const KEY_PREFIX = "recall.list-group-order.";

function storageKey(userId: string): string {
  const safe = userId.replace(/[^a-zA-Z0-9._-]/g, "_");
  return `${KEY_PREFIX}${safe || "default"}`;
}

function filePath(userId: string): string | null {
  if (!documentDirectory) return null;
  return `${documentDirectory}${storageKey(userId)}.json`;
}

function parseTopics(raw: string): string[] {
  const parsed = JSON.parse(raw) as unknown;
  if (!Array.isArray(parsed)) return [];
  return parsed.filter((value): value is string => typeof value === "string");
}

async function loadLegacySecureStore(userId: string): Promise<string[]> {
  try {
    const raw = await SecureStore.getItemAsync(storageKey(userId));
    if (!raw) return [];
    return parseTopics(raw);
  } catch {
    return [];
  }
}

export async function loadListGroupOrder(userId: string): Promise<string[]> {
  const path = filePath(userId);
  if (path) {
    try {
      const info = await getInfoAsync(path);
      if (info.exists) {
        return parseTopics(await readAsStringAsync(path));
      }
    } catch {
      /* fall through to legacy */
    }
  }

  const legacy = await loadLegacySecureStore(userId);
  if (legacy.length > 0) {
    await saveListGroupOrder(userId, legacy);
  }
  return legacy;
}

export async function saveListGroupOrder(userId: string, topics: string[]): Promise<void> {
  const path = filePath(userId);
  if (!path) return;
  try {
    await writeAsStringAsync(path, JSON.stringify(topics));
  } catch {
    /* best-effort — in-memory order from the caller still applies this session */
  }
}
