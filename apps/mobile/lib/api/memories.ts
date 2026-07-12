import { request } from "@/lib/api/client";
import type { Memory } from "@/lib/api/types";

export const memoriesApi = {
  listMemories: (token: string) => request<Memory[]>("/memories", token),
  deleteMemorySection: (token: string, type: string) =>
    request<void>(`/memories/type/${type}`, token, { method: "DELETE" }),
  // BUG FIX (was silent): factIndex alone can go stale — a background
  // extraction/consolidation job may rewrite this section between when this
  // screen loaded it and when the user taps delete, shifting which fact sits
  // at that index. Sending factText (what the user actually saw and tapped)
  // lets the server locate the fact by content instead of trusting a
  // possibly-stale position.
  deleteMemoryFact: (token: string, memoryId: string, factIndex: number, factText: string) =>
    request<void>(
      `/memories/${memoryId}/facts/${factIndex}?fact_text=${encodeURIComponent(factText)}`,
      token,
      { method: "DELETE" },
    ),
};
