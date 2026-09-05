import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, type Memory } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { joinMemoryFacts, splitMemoryFacts } from "@/lib/memoryFacts";
import { fetchMemories, getCachedMemories, updateMemoriesCache } from "@/lib/cache/memoryListCache";

export type LoadOptions = { silent?: boolean; force?: boolean };
type MemoryUpdate = (rows: Memory[]) => Memory[];

let mutationSession = -1;
let pendingTypes = new Set<string>();
const mutationListeners = new Set<(error?: boolean) => void>();
function sessionPendingTypes(session: number): Set<string> {
  if (mutationSession !== session) {
    mutationSession = session;
    pendingTypes = new Set();
  }
  return pendingTypes;
}
function notifyMutation(error?: boolean): void {
  mutationListeners.forEach((listener) => listener(error));
}

function restoreRows(rows: Memory[], snapshots: Memory[]): Memory[] {
  const restored = rows.map((row) => snapshots.find((saved) => saved.id === row.id) ?? row);
  return [...restored, ...snapshots.filter((saved) => !rows.some((row) => row.id === saved.id))];
}

function normalizeFact(text: string): string {
  return text.trim().replace(/\s+/g, " ").replace(/\.+$/, "").toLowerCase();
}

/** Account-owned list state; independent sections can mutate without replacing each other. */
export function useMemoryActions(token: string | null) {
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const owner = useMemo(() => {
    const cached = signedIn ? getCachedMemories() : undefined;
    return {
      session, signedIn, pending: sessionPendingTypes(session),
      initial: { memories: cached ?? [], loading: signedIn && !cached, error: false },
    };
  }, [session, signedIn]);
  const ownerRef = useRef(owner);
  ownerRef.current = owner;
  const loadingState = useRef({ owner, loadId: 0, hasLoaded: !owner.initial.loading });
  if (loadingState.current.owner !== owner) {
    loadingState.current = { owner, loadId: 0, hasLoaded: !owner.initial.loading };
  }
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const [state, setState] = useState({ ...owner.initial, owner, pendingTypes: new Set(owner.pending) });
  const view = state.owner === owner ? state : { ...owner.initial, pendingTypes: new Set(owner.pending) };
  const isSameOwner = useCallback(() =>
    owner.signedIn && ownerRef.current === owner && getSessionGeneration() === owner.session,
  [owner]);
  const isCurrentOwner = useCallback(() => mounted.current && isSameOwner(), [isSameOwner]);
  const publish = useCallback((patch: Partial<typeof owner.initial> = {}) => {
    if (!isCurrentOwner()) return;
    setState((previous) => ({
      ...(previous.owner === owner ? previous : owner.initial),
      ...patch, owner, pendingTypes: new Set(owner.pending),
    }));
  }, [isCurrentOwner, owner]);
  useEffect(() => {
    const changed = (error?: boolean) => publish({
      memories: getCachedMemories() ?? [], ...(error == null ? {} : { error }),
    });
    mutationListeners.add(changed);
    return () => { mutationListeners.delete(changed); };
  }, [publish]);
  const applyUpdate = useCallback((update: MemoryUpdate) => {
    if (!isSameOwner()) return;
    // A completed request still reconciles the same account's cache after navigation.
    const memories = updateMemoriesCache(update, owner.session);
    publish({ memories });
    notifyMutation();
  }, [isSameOwner, owner, publish]);

  const load = useCallback(async (opts?: LoadOptions) => {
    if (!token || !isCurrentOwner()) return;
    const request = ++loadingState.current.loadId;
    const showSkeleton = !opts?.silent && !loadingState.current.hasLoaded && !getCachedMemories()?.length;
    publish({ error: false, ...(showSkeleton ? { loading: true } : {}) });
    const data = await fetchMemories(token, { force: opts?.force });
    if (!isCurrentOwner() || request !== loadingState.current.loadId) return;
    loadingState.current.hasLoaded = true;
    publish({
      ...(data ? { memories: getCachedMemories() ?? data } : {}),
      error: data === null, loading: false,
    });
  }, [token, isCurrentOwner, publish]);

  const mutate = useCallback(async (
    type: string,
    optimistic: MemoryUpdate,
    rollback: MemoryUpdate,
    request: () => Promise<MemoryUpdate>,
  ): Promise<boolean> => {
    if (!isCurrentOwner() || owner.pending.has(type)) return false;
    owner.pending.add(type);
    applyUpdate(optimistic);
    try {
      const confirmed = await request();
      // Reaffirm over GETs started after the optimistic change but before commit.
      applyUpdate(confirmed);
      return isCurrentOwner();
    } catch {
      applyUpdate(rollback);
      if (token && isSameOwner()) {
        // A failed response can hide a committed write or a concurrent change.
        // Settle reads carrying rollback before requesting authoritative rows.
        void fetchMemories(token, { force: true, afterPending: true }).then((data) => {
          if (isSameOwner()) notifyMutation(data === null);
        });
      }
      return false;
    } finally {
      owner.pending.delete(type);
      if (isSameOwner()) notifyMutation();
    }
  }, [token, isCurrentOwner, isSameOwner, owner, applyUpdate]);

  const deleteSection = useCallback(async (type: string): Promise<boolean> => {
    if (!token || !isCurrentOwner()) return false;
    const snapshots = getCachedMemories()?.filter((row) => row.type === type) ?? [];
    if (!snapshots.length) return false;
    const remove: MemoryUpdate = (rows) => rows.filter((row) => row.type !== type);
    return mutate(type, remove, (rows) => restoreRows(rows, snapshots), async () => {
      await api.deleteMemorySection(token, type);
      return remove;
    });
  }, [token, isCurrentOwner, mutate]);

  const deleteFact = useCallback(async (
    section: Memory, factIndex: number, factText: string,
  ): Promise<boolean> => {
    if (!token || !isCurrentOwner()) return false;
    const snapshot = getCachedMemories()?.find((row) => row.id === section.id);
    if (!snapshot) return false;
    const facts = splitMemoryFacts(snapshot.text);
    const expected = normalizeFact(factText);
    const matches = facts.map((fact, index) => normalizeFact(fact) === expected ? index : -1)
      .filter((index) => index >= 0);
    const targetIndex = matches.includes(factIndex) ? factIndex : matches[0];
    if (targetIndex == null) return false;
    const remove: MemoryUpdate = (rows) => rows.flatMap((row) => {
      if (row.id !== snapshot.id) return [row];
      const currentFacts = splitMemoryFacts(row.text);
      const currentMatches = currentFacts.map((fact, index) => normalizeFact(fact) === expected ? index : -1)
        .filter((index) => index >= 0);
      // The same updater runs optimistically and again over an in-flight GET.
      if (currentMatches.length < matches.length) return [row];
      currentFacts.splice(currentMatches.includes(targetIndex) ? targetIndex : currentMatches[0], 1);
      return currentFacts.length ? [{ ...row, text: joinMemoryFacts(currentFacts) }] : [];
    });
    const restore: MemoryUpdate = (rows) => {
      const row = rows.find((item) => item.id === snapshot.id);
      if (!row) return restoreRows(rows, [snapshot]);
      const currentFacts = splitMemoryFacts(row.text);
      if (currentFacts.filter((fact) => normalizeFact(fact) === expected).length >= matches.length) return rows;
      const nextFact = facts[targetIndex + 1];
      const before = nextFact == null ? -1 : currentFacts.findIndex((fact) => normalizeFact(fact) === normalizeFact(nextFact));
      currentFacts.splice(before >= 0 ? before : Math.min(targetIndex, currentFacts.length), 0, facts[targetIndex]);
      return restoreRows(rows, [{ ...row, text: joinMemoryFacts(currentFacts) }]);
    };
    return mutate(snapshot.type, remove, restore, async () => {
      await api.deleteMemoryFact(token, snapshot.id, targetIndex, factText);
      return remove;
    });
  }, [token, isCurrentOwner, mutate]);

  const updateMemoryText = useCallback(async (memoryId: string, nextText: string): Promise<boolean> => {
    if (!token || !isCurrentOwner()) return false;
    const snapshot = getCachedMemories()?.find((row) => row.id === memoryId);
    if (!snapshot) return false;
    return mutate(snapshot.type,
      (rows) => restoreRows(rows, [{ ...snapshot, text: nextText }]),
      (rows) => restoreRows(rows, [snapshot]),
      async () => {
        const updated = await api.updateMemory(token, memoryId, nextText);
        return (rows) => restoreRows(rows, [updated]);
      });
  }, [token, isCurrentOwner, mutate]);

  const hasLoaded = useCallback(() => isCurrentOwner() && loadingState.current.hasLoaded, [isCurrentOwner]);
  return { memories: view.memories, loading: view.loading, error: view.error,
    pendingTypes: view.pendingTypes, load, hasLoaded, isCurrentOwner, deleteSection, deleteFact, updateMemoryText };
}
