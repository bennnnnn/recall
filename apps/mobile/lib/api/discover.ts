import { request } from "@/lib/api/client";
import type { ModelInfo, Suggestion, Usage } from "@/lib/api/types";

export const discoverApi = {
  todayUsage: (token: string) => request<Usage>("/chats/usage/today", token),
  listModels: (token: string) => request<ModelInfo[]>("/models", token),
  listSuggestions: (token: string) => request<Suggestion[]>("/suggestions", token),
  dismissSuggestion: (token: string, id: string) =>
    request<void>(`/suggestions/${id}/dismiss`, token, { method: "POST" }),
};
