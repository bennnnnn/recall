/**
 * Non-secret preference persistence. Filesystem is primary; SecureStore is
 * a one-shot migration read. Keychain writes fail on unsigned simulator
 * builds (errSecMissingEntitlement / -34018).
 */
import {
  deleteAsync,
  documentDirectory,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";
import * as SecureStore from "expo-secure-store";

export function prefFilePath(fileName: string): string | null {
  if (!documentDirectory) return null;
  return `${documentDirectory}${fileName}`;
}

export function safePrefUserId(userId: string): string {
  return userId.replace(/[^a-zA-Z0-9._-]/g, "_") || "default";
}

export async function readPrefFile(path: string | null): Promise<string | null> {
  if (!path) return null;
  try {
    const info = await getInfoAsync(path);
    if (!info.exists) return null;
    return await readAsStringAsync(path);
  } catch {
    return null;
  }
}

export async function writePrefFile(path: string | null, value: string): Promise<void> {
  if (!path) return;
  try {
    await writeAsStringAsync(path, value);
  } catch {
    /* best-effort — in-memory state from the caller still applies this session */
  }
}

export async function deletePrefFile(path: string | null): Promise<void> {
  if (!path) return;
  try {
    await deleteAsync(path, { idempotent: true });
  } catch {
    /* best-effort */
  }
}

export async function readLegacySecureStore(key: string): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    return null;
  }
}

export async function deleteLegacySecureStore(key: string): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(key);
  } catch {
    /* best-effort */
  }
}
