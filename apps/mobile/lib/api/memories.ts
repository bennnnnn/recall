import { request } from "@/lib/api/client";
import type { Memory } from "@/lib/api/types";

// Saved text can contain 4000 code points plus an "As of YYYY-MM-DD: " stamp.
export const MAX_MEMORY_FACT_TEXT_LENGTH = 4018;

export const memoriesApi = {
  listMemories: (token: string) => request<Memory[]>("/memories", token),
  updateMemory: (token: string, memoryId: string, text: string) =>
    request<Memory>(`/memories/${memoryId}`, token, {
      method: "PATCH",
      body: JSON.stringify({ text }),
    }),
  deleteMemorySection: (token: string, type: string) =>
    request<void>(`/memories/type/${type}`, token, { method: "DELETE" }),
  // BUG FIX (was silent): factIndex alone can go stale — a background
  // extraction/consolidation job may rewrite this section between when this
  // screen loaded it and when the user taps delete, shifting which fact sits
  // at that index. Sending factText (what the user actually saw and tapped)
  // lets the server locate the fact by content instead of trusting a
  // possibly-stale position.
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
