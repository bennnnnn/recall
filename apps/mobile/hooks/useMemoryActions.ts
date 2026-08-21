import { useCallback, useRef, useState } from "react";

import { api, Memory } from "@/lib/api";
import { joinMemoryFacts, splitMemoryFacts } from "@/lib/memoryFacts";
import {
  fetchMemories,
  getCachedMemories,
  setMemoriesCache,
} from "@/lib/cache/memoryListCache";

export type LoadOptions = { silent?: boolean; force?: boolean };

/**
 * Memory list state plus its optimistic mutations.
 *
 * Each mutation applies the change locally, calls the API, and rolls back on
 * failure; callers get a boolean so the screen owns the user-facing Alert and
 * its i18n. Keeping this out of the screen makes the rollback paths testable —
 * they used to live inside Alert callbacks nested six levels into the render
 * tree, where nothing could reach them.
 */
export function useMemoryActions(token: string | null) {
  const cachedOnMount = getCachedMemories();
  const [memories, setMemories] = useState<Memory[]>(() => cachedOnMount ?? []);
  const [loading, setLoading] = useState(() => !cachedOnMount);
  const [error, setError] = useState(false);
  const hasLoadedRef = useRef(Boolean(cachedOnMount));

  const applyMemories = useCallback((next: Memory[]) => {
    setMemories(next);
    setMemoriesCache(next);
  }, []);

  const load = useCallback(
    async (opts?: LoadOptions) => {
      if (!token) {
        setLoading(false);
        return;
      }
      const showSkeleton =
        !opts?.silent && !hasLoadedRef.current && !getCachedMemories()?.length;
      if (showSkeleton) setLoading(true);
      setError(false);
      const data = await fetchMemories(token, { force: opts?.force });
      if (data) {
        setMemories(data);
      } else if (!getCachedMemories()?.length) {
        setError(true);
      }
      hasLoadedRef.current = true;
      if (showSkeleton) setLoading(false);
    },
    [token],
  );

  const hasLoaded = useCallback(() => hasLoadedRef.current, []);

  const deleteSection = useCallback(
    async (type: string): Promise<boolean> => {
      if (!token) return false;
      const snapshot = memories;
      applyMemories(memories.filter((item) => item.type !== type));
      try {
        await api.deleteMemorySection(token, type);
        return true;
      } catch {
        applyMemories(snapshot);
        return false;
      }
    },
    [token, memories, applyMemories],
  );

  const deleteFact = useCallback(
    async (section: Memory, factIndex: number, factText: string): Promise<boolean> => {
      if (!token) return false;
      const snapshot = memories;
      const facts = splitMemoryFacts(section.text);
      facts.splice(factIndex, 1);
      if (facts.length === 0) {
        applyMemories(memories.filter((item) => item.id !== section.id));
      } else {
        const nextText = joinMemoryFacts(facts);
        applyMemories(
          memories.map((item) =>
            item.id === section.id ? { ...item, text: nextText } : item,
          ),
        );
      }
      try {
        await api.deleteMemoryFact(token, section.id, factIndex, factText);
        return true;
      } catch {
        // A 404 here can mean a background job already changed this fact (see
        // the server-side content-match fix) — reload from the server instead
        // of trusting our now-stale snapshot, so the user sees what's actually
        // there.
        applyMemories(snapshot);
        void load({ silent: true, force: true });
        return false;
      }
    },
    [token, memories, applyMemories, load],
  );

  const updateMemoryText = useCallback(
    async (memoryId: string, nextText: string): Promise<boolean> => {
      if (!token) return false;
      const snapshot = memories;
      applyMemories(
        memories.map((item) => (item.id === memoryId ? { ...item, text: nextText } : item)),
      );
      try {
        const updated = await api.updateMemory(token, memoryId, nextText);
        // Prefer server text (includes the as-of stamp) over the optimistic draft.
        applyMemories(snapshot.map((item) => (item.id === updated.id ? updated : item)));
        return true;
      } catch {
        applyMemories(snapshot);
        return false;
      }
    },
    [token, memories, applyMemories],
  );

  return {
    memories,
    loading,
    error,
    load,
    hasLoaded,
    applyMemories,
    deleteSection,
    deleteFact,
    updateMemoryText,
  };
}
