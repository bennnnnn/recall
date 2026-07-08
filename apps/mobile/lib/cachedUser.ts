import {
  cacheDirectory,
  deleteAsync,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

import type { User } from "@/lib/api/types";

const CACHED_USER_PATH = `${cacheDirectory ?? ""}cached-user.json`;

/** Last-known user, used to paint the app instantly on cold start instead of
 * blocking the whole navigator behind an api.me() round trip. Best-effort —
 * the cache directory can be purged by the OS at any time, in which case
 * cold start just falls back to the normal loading state. */
export async function readCachedUser(): Promise<User | null> {
  if (!cacheDirectory) return null;
  try {
    const info = await getInfoAsync(CACHED_USER_PATH);
    if (!info.exists) return null;
    const raw = await readAsStringAsync(CACHED_USER_PATH);
    const parsed = JSON.parse(raw) as User;
    if (!parsed || typeof parsed.id !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}

export async function writeCachedUser(user: User): Promise<void> {
  if (!cacheDirectory) return;
  try {
    await writeAsStringAsync(CACHED_USER_PATH, JSON.stringify(user));
  } catch {
    /* best-effort */
  }
}

export async function clearCachedUser(): Promise<void> {
  if (!cacheDirectory) return;
  try {
    await deleteAsync(CACHED_USER_PATH, { idempotent: true });
  } catch {
    /* ignore */
  }
}
