import { useCallback } from "react";

import { api } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { getCachedMemoryDocuments, setMemoryDocuments } from "@/features/memory/model/memoryDocumentsCache";
import { invalidateMemoriesCache } from "@/features/memory/model/memoryListCache";
import { memoryFailure, type MemoryFailure } from "@/features/memory/model/memoryFailure";
import {
  instructFailure,
  mayStillBeSaving,
  noteInstructAnswered,
  noteInstructUnanswered,
  unansweredSince,
} from "@/features/memory/model/instructInFlight";

type InstructOutcome =
  | { ok: true; reply: string; applied: number; dropped: number }
  | { ok: false; failure: MemoryFailure };

/**
 * The memory box's edit in plain words ("keep lists under five things"): its pages land
 * from the answer. A retry that meets the memory lock soon after an edit from here went
 * unanswered is that edit still saving, not a failure (`instructInFlight.ts`).
 */
export function useMemoryInstruct(token: string | null) {
  return useCallback(async (instruction: string, topic?: string): Promise<InstructOutcome> => {
    if (!token) return { ok: false, failure: "failed" };
    const session = getSessionGeneration();
    try {
      const result = await api.instructMemory(token, instruction, topic);
      noteInstructAnswered();
      const scanning = getCachedMemoryDocuments()?.scanning ?? false;
      setMemoryDocuments({ documents: result.documents, scanning }, session);
      invalidateMemoriesCache();
      return { ok: true, reply: result.reply, applied: result.applied, dropped: result.dropped ?? 0 };
    } catch (error) {
      const failure = instructFailure(memoryFailure(error), unansweredSince());
      // Sent and not answered in time: the server may still be saving it, under the lock.
      if (mayStillBeSaving(error)) noteInstructUnanswered();
      return { ok: false, failure };
    }
  }, [token]);
}
