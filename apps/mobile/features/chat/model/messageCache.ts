import {
  cacheDirectory,
  deleteAsync,
  getInfoAsync,
  makeDirectoryAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

import type { Message } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";

export type CachedChatPage = {
  messages: Message[];
  has_more: boolean;
  cached_at: string;
};

const CACHE_DIR = `${cacheDirectory ?? ""}chat-pages/`;
let diskWrites: Promise<void> = Promise.resolve();
let clearGeneration = 0;
const chatClearGenerations = new Map<string, number>();

function cacheIsCurrent(chatId: string): () => boolean {
  const session = getSessionGeneration();
  const all = clearGeneration;
  const chat = chatClearGenerations.get(chatId);
  return () => session === getSessionGeneration() && all === clearGeneration &&
    chat === chatClearGenerations.get(chatId);
}

// A delete must run after an already-started write. Patches share this queue so
// their read-modify-write cannot overwrite a newer page fetched from the server.
function mutateDisk(mutation: () => Promise<void>): Promise<void> {
  diskWrites = diskWrites.then(mutation).catch(() => { /* best-effort cache */ });
  return diskWrites;
}

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

export function cachedChatPageFetchedAt(
  cached: Pick<CachedChatPage, "cached_at"> | null | undefined,
): number | undefined {
  if (!cached?.cached_at) return undefined;
  const at = Date.parse(cached.cached_at);
  return Number.isFinite(at) ? at : undefined;
}

export async function readCachedChatMessages(chatId: string): Promise<CachedChatPage | null> {
  if (!cacheDirectory) return null;
  const isCurrent = cacheIsCurrent(chatId);
  try {
    const info = await getInfoAsync(cachePath(chatId));
    if (!info.exists) return null;
    const raw = await readAsStringAsync(cachePath(chatId));
    const parsed = JSON.parse(raw) as CachedChatPage;
    if (!isCurrent() || !Array.isArray(parsed.messages)) return null;
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
  const isCurrent = cacheIsCurrent(chatId);
  return mutateDisk(async () => {
    if (!isCurrent()) return;
    await ensureDir();
    if (!isCurrent()) return;
    const payload: CachedChatPage = {
      messages,
      has_more: hasMore,
      cached_at: new Date().toISOString(),
    };
    await writeAsStringAsync(cachePath(chatId), JSON.stringify(payload));
  });
}

export async function patchCachedChatMessage(
  chatId: string,
  messageId: string,
  patch: Partial<Message>,
): Promise<void> {
  if (!cacheDirectory) return;
  const isCurrent = cacheIsCurrent(chatId);
  return mutateDisk(async () => {
    if (!isCurrent()) return;
    const cached = await readCachedChatMessages(chatId);
    if (!cached || !isCurrent()) return;
    const messages = cached.messages.map((m) =>
      m.id === messageId ? { ...m, ...patch } : m,
    );
    await writeAsStringAsync(cachePath(chatId), JSON.stringify({ ...cached, messages }));
  });
}

export async function clearCachedChatMessages(chatId: string): Promise<void> {
  chatClearGenerations.set(chatId, (chatClearGenerations.get(chatId) ?? 0) + 1);
  if (!cacheDirectory) return;
  return mutateDisk(async () => {
    await deleteAsync(cachePath(chatId), { idempotent: true });
  });
}

export async function clearAllCachedChatMessages(): Promise<void> {
  clearGeneration++;
  chatClearGenerations.clear();
  if (!cacheDirectory) return;
  return mutateDisk(async () => {
    const info = await getInfoAsync(CACHE_DIR);
    if (!info.exists) return;
    await deleteAsync(CACHE_DIR, { idempotent: true });
  });
}
