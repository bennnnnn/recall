import { request } from "@/lib/api/client";
import type { Memory } from "@/lib/api/types";
import type { MemoryDocuments, MemoryInstructResult } from "@/features/memory/types";

export const MAX_MEMORY_FACT_TEXT_LENGTH = 4018;

export type MemoryPatch = {
  text?: string;
  status?: "active" | "muted" | "superseded";
};

export const memoriesApi = {
  listMemories: (token: string) => request<Memory[]>("/memories", token),
  listMemoryDocuments: (token: string) =>
    request<MemoryDocuments>("/memories/documents", token),
  deleteMemoryDocument: (token: string, key: string) =>
    request<void>(`/memories/documents/${encodeURIComponent(key)}`, token, { method: "DELETE" }),
  /** Edit memory in plain words ("keep lists under five things"). */
  instructMemory: (token: string, instruction: string, topic?: string) =>
    request<MemoryInstructResult>("/memories/instruct", token, {
      method: "POST",
      body: JSON.stringify(topic ? { instruction, topic } : { instruction }),
    }),
  updateMemory: (token: string, memoryId: string, patch: string | MemoryPatch) =>
    request<Memory>(`/memories/${memoryId}`, token, {
      method: "PATCH",
      body: JSON.stringify(typeof patch === "string" ? { text: patch } : patch),
    }),
  deleteMemory: (token: string, memoryId: string) =>
    request<void>(`/memories/${memoryId}`, token, { method: "DELETE" }),
  deleteMemorySection: (token: string, type: string) =>
    request<void>(`/memories/type/${type}`, token, { method: "DELETE" }),
  clearMemories: (token: string) =>
    request<void>("/memories", token, { method: "DELETE" }),
  deleteMemoryFact: async (token: string, memoryId: string, factIndex: number, factText: string) => {
    if ([...factText].length > MAX_MEMORY_FACT_TEXT_LENGTH) {
      throw new RangeError("Memory fact text exceeds the deletion selector limit");
    }
    const query = new URLSearchParams({ fact_text: factText });
    return request<void>(
      `/memories/${memoryId}/facts/${factIndex}?${query.toString()}`,
      token,
      { method: "DELETE" },
    );
  },
};
