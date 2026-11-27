import { request, requestRevalidated } from "@/lib/api/client";
import { confirmedDelete } from "@/lib/api/confirmedDelete";
import { apiPath } from "@/lib/api/path";
import type { Memory } from "@/lib/api/types";
import type { MemoryDocuments, MemoryInstructResult } from "@/features/memory/types";

/**
 * How long a typed memory edit is waited for: the server's model budget for it
 * (apps/api core/settings/memory.py memory_instruct_model_seconds, 45 s) and its writes.
 * The 30 s default gave up while the server worked on, and the retry met the edit's lock.
 */
export const INSTRUCT_TIMEOUT_MS = 75_000;

type MemoryPatch = {
  text?: string;
  status?: "active" | "muted" | "superseded";
};

export const memoriesApi = {
  listMemories: (token: string) => request<Memory[]>("/memories", token),
  /** Read on every visit and scan poll; unchanged pages are a 304 by their ETag. */
  listMemoryDocuments: (token: string) =>
    requestRevalidated<MemoryDocuments>("/memories/documents", token),
  deleteMemoryDocument: (token: string, key: string) =>
    request<void>(apiPath`/memories/documents/${key}`, token, { method: "DELETE" }),
  /** Edit memory in plain words ("keep lists under five things"). */
  instructMemory: (token: string, instruction: string, topic?: string) =>
    request<MemoryInstructResult>(
      "/memories/instruct",
      token,
      {
        method: "POST",
        body: JSON.stringify(topic ? { instruction, topic } : { instruction }),
      },
      true,
      INSTRUCT_TIMEOUT_MS,
    ),
  updateMemory: (token: string, memoryId: string, patch: string | MemoryPatch) =>
    request<Memory>(apiPath`/memories/${memoryId}`, token, {
      method: "PATCH",
      body: JSON.stringify(typeof patch === "string" ? { text: patch } : patch),
    }),
  deleteMemory: (token: string, memoryId: string) =>
    request<void>(apiPath`/memories/${memoryId}`, token, { method: "DELETE" }),
  /** Called only after the user confirmed it, and says so (`confirmedDelete`). */
  clearMemories: (token: string) => request<void>("/memories", token, confirmedDelete()),
};
