import {
  cacheDirectory,
  deleteAsync,
  getInfoAsync,
  makeDirectoryAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

import type { Message } from "@/lib/api";

export type CachedChatPage = {
  messages: Message[];
  has_more: boolean;
  cached_at: string;
};

const CACHE_DIR = `${cacheDirectory ?? ""}chat-pages/`;

function cachePath(chatId: string): string {
  return `${CACHE_DIR}${chatId}.json`;
}

async function ensureDir(): Promise<void> {
  if (!cacheDirectory) return;
  const info = await getInfoAsync(CACHE_DIR);
  if (!info.exists) {
    await makeDirectoryAsync(CACHE_DIR, { intermediates: true });
  }
}

export async function readCachedChatMessages(chatId: string): Promise<CachedChatPage | null> {
  if (!cacheDirectory) return null;
  try {
    const info = await getInfoAsync(cachePath(chatId));
    if (!info.exists) return null;
    const raw = await readAsStringAsync(cachePath(chatId));
    const parsed = JSON.parse(raw) as CachedChatPage;
    if (!Array.isArray(parsed.messages)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export async function writeCachedChatMessages(
  chatId: string,
  messages: Message[],
  hasMore: boolean,
): Promise<void> {
  if (!cacheDirectory) return;
  try {
    await ensureDir();
    const payload: CachedChatPage = {
      messages,
      has_more: hasMore,
      cached_at: new Date().toISOString(),
    };
    await writeAsStringAsync(cachePath(chatId), JSON.stringify(payload));
  } catch {
    /* best-effort */
  }
}

export async function clearCachedChatMessages(chatId: string): Promise<void> {
  if (!cacheDirectory) return;
  try {
    await deleteAsync(cachePath(chatId), { idempotent: true });
  } catch {
    /* ignore */
  }
}

export async function clearAllCachedChatMessages(): Promise<void> {
  if (!cacheDirectory) return;
  try {
    const info = await getInfoAsync(CACHE_DIR);
    if (!info.exists) return;
    await deleteAsync(CACHE_DIR, { idempotent: true });
  } catch {
    /* best-effort */
  }
}
