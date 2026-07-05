import { request } from "@/lib/api/client";
import type { Memory } from "@/lib/api/types";

export const memoriesApi = {
  listMemories: (token: string) => request<Memory[]>("/memories", token),
  deleteMemorySection: (token: string, type: string) =>
    request<void>(`/memories/type/${type}`, token, { method: "DELETE" }),
  deleteMemoryFact: (token: string, memoryId: string, factIndex: number) =>
    request<void>(`/memories/${memoryId}/facts/${factIndex}`, token, {
      method: "DELETE",
    }),
};
