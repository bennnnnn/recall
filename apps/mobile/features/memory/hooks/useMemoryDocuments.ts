import { useCallback, useEffect, useRef, useState } from "react";

import { api, type Memory } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import {
  fetchMemoryDocuments,
  getCachedMemoryDocuments,
  setMemoryDocuments,
  subscribeMemoryDocuments,
  updateMemoryDocuments,
} from "@/features/memory/model/memoryDocumentsCache";
import { invalidateMemoriesCache } from "@/features/memory/model/memoryListCache";
import type { MemoryDocument, MemoryDocuments } from "@/features/memory/types";

export type InstructOutcome = { ok: true; reply: string } | { ok: false };

function withoutFact(documents: MemoryDocument[], factId: string): MemoryDocument[] {
  return documents
    .map((document) => ({
      ...document,
      facts: document.facts.filter((fact) => fact.id !== factId),
    }))
    .filter((document) => document.facts.length > 0);
}

function withFact(documents: MemoryDocument[], updated: Memory): MemoryDocument[] {
  return documents.map((document) => ({
    ...document,
    facts: document.facts.map((fact) => (fact.id === updated.id ? { ...fact, ...updated } : fact)),
  }));
}

type FactPlace = { document: MemoryDocument; fact: Memory; index: number };

function findFact(documents: MemoryDocument[], factId: string): FactPlace | undefined {
  for (const document of documents) {
    const index = document.facts.findIndex((fact) => fact.id === factId);
    if (index >= 0) return { document, fact: document.facts[index], index };
  }
  return undefined;
}

/** Put one removed fact back where it was, keeping every other change. */
function withFactRestored(documents: MemoryDocument[], place: FactPlace): MemoryDocument[] {
  if (findFact(documents, place.fact.id)) return documents;
  if (!documents.some((document) => document.key === place.document.key)) {
    return [...documents, { ...place.document, facts: [place.fact] }];
  }
  return documents.map((document) => {
    if (document.key !== place.document.key) return document;
    const facts = [...document.facts];
    facts.splice(Math.min(place.index, facts.length), 0, place.fact);
    return { ...document, facts };
  });
}

function withDocumentRestored(
  documents: MemoryDocument[],
  removed: MemoryDocument,
): MemoryDocument[] {
  return documents.some((document) => document.key === removed.key)
    ? documents
    : [...documents, removed];
}

/**
 * Memory as documents (You, Topics, Areas) for the signed-in account. Writes
 * made after an account switch never land in the next account's pages.
 */
export function useMemoryDocuments(token: string | null) {
  const [data, setData] = useState<MemoryDocuments | undefined>(() => getCachedMemoryDocuments());
  const [loaded, setLoaded] = useState(Boolean(data));
  const [error, setError] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => subscribeMemoryDocuments(() => {
    if (mounted.current) setData(getCachedMemoryDocuments());
  }), []);

  const load = useCallback(async () => {
    if (!token) return;
    setError(false);
    const result = await fetchMemoryDocuments(token);
    if (!mounted.current) return;
    setLoaded(true);
    if (result === null && !getCachedMemoryDocuments()) setError(true);
  }, [token]);

  const instruct = useCallback(async (
    instruction: string,
    topic?: string,
  ): Promise<InstructOutcome> => {
    if (!token) return { ok: false };
    const session = getSessionGeneration();
    try {
      const result = await api.instructMemory(token, instruction, topic);
      const scanning = getCachedMemoryDocuments()?.scanning ?? false;
      setMemoryDocuments({ documents: result.documents, scanning }, session);
      invalidateMemoriesCache();
      return { ok: true, reply: result.reply };
    } catch {
      return { ok: false };
    }
  }, [token]);

  const removeOptimistically = useCallback(async (
    remove: (documents: MemoryDocument[]) => MemoryDocument[],
    restore: (documents: MemoryDocument[]) => MemoryDocument[],
    request: () => Promise<void>,
  ): Promise<boolean> => {
    const session = getSessionGeneration();
    updateMemoryDocuments(remove, session);
    try {
      await request();
      // A refresh that landed mid-request may have brought the item back.
      updateMemoryDocuments(remove, session);
      invalidateMemoriesCache();
      return true;
    } catch {
      // Put back only this item: other deletes may have finished meanwhile.
      updateMemoryDocuments(restore, session);
      return false;
    }
  }, []);

  const deleteDocument = useCallback(async (key: string): Promise<boolean> => {
    if (!token) return false;
    const removed = getCachedMemoryDocuments()?.documents.find((document) => document.key === key);
    return removeOptimistically(
      (documents) => documents.filter((document) => document.key !== key),
      (documents) => (removed ? withDocumentRestored(documents, removed) : documents),
      () => api.deleteMemoryDocument(token, key),
    );
  }, [token, removeOptimistically]);

  const deleteFact = useCallback(async (factId: string): Promise<boolean> => {
    if (!token) return false;
    const place = findFact(getCachedMemoryDocuments()?.documents ?? [], factId);
    return removeOptimistically(
      (documents) => withoutFact(documents, factId),
      (documents) => (place ? withFactRestored(documents, place) : documents),
      () => api.deleteMemory(token, factId),
    );
  }, [token, removeOptimistically]);

  const editFact = useCallback(async (factId: string, text: string): Promise<boolean> => {
    if (!token) return false;
    const session = getSessionGeneration();
    try {
      const updated = await api.updateMemory(token, factId, text);
      updateMemoryDocuments((documents) => withFact(documents, updated), session);
      invalidateMemoriesCache();
      return true;
    } catch {
      return false;
    }
  }, [token]);

  return {
    documents: data?.documents ?? [],
    scanning: data?.scanning ?? false,
    loading: !loaded && !data,
    error: error && !data,
    load,
    instruct,
    deleteDocument,
    deleteFact,
    editFact,
  };
}
