import { api } from "@/lib/api";
import { getSessionGeneration, requireTokenSession } from "@/lib/auth";
import type { MemoryDocument, MemoryDocuments } from "@/features/memory/types";

type CacheState = {
  session: number;
  data?: MemoryDocuments;
  pending?: Promise<MemoryDocuments | null>;
};

let cache: CacheState = { session: -1 };
const listeners = new Set<() => void>();

function notify(): void {
  listeners.forEach((listener) => listener());
}

function currentCache(): CacheState {
  // A new account starts empty; the old account's pages are dropped here.
  if (cache.session !== getSessionGeneration()) cache = { session: getSessionGeneration() };
  return cache;
}

export function subscribeMemoryDocuments(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function getCachedMemoryDocuments(): MemoryDocuments | undefined {
  return currentCache().data;
}

/** Replace the pages, unless the account changed since the caller's request began. */
export function setMemoryDocuments(data: MemoryDocuments, expectedSession: number): void {
  const state = currentCache();
  if (state.session !== expectedSession) return;
  state.data = data;
  notify();
}

export function updateMemoryDocuments(
  update: (documents: MemoryDocument[]) => MemoryDocument[],
  expectedSession: number,
): void {
  const state = currentCache();
  if (state.session !== expectedSession || !state.data) return;
  state.data = { ...state.data, documents: update(state.data.documents) };
  notify();
}

export function invalidateMemoryDocuments(): void {
  cache = { session: getSessionGeneration() };
  notify();
}

export async function fetchMemoryDocuments(token: string): Promise<MemoryDocuments | null> {
  try { requireTokenSession(token); } catch { return null; }
  const state = currentCache();
  if (state.pending) return state.pending;
  const task = (async () => {
    try {
      const data = await api.listMemoryDocuments(token);
      if (currentCache() !== state) return null;
      state.data = data;
      notify();
      return data;
    } catch {
      return null;
    }
  })();
  state.pending = task;
  try { return await task; }
  finally { if (state.pending === task) state.pending = undefined; }
}
