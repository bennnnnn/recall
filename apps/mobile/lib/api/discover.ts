import { request } from "@/lib/api/client";
import type {
  HomeScreen,
  ModelInfo,
  SearchResult,
  Suggestion,
  Usage,
} from "@/lib/api/types";

export const discoverApi = {
  todayUsage: (token: string) => request<Usage>("/chats/usage/today", token),
  listModels: (token: string) => request<ModelInfo[]>("/models", token),
  search: (token: string, q: string, limit = 20, init?: Pick<RequestInit, "signal">) =>
    request<{ results: SearchResult[]; total: number }>(
      `/search?q=${encodeURIComponent(q)}&limit=${limit}`,
      token,
      init,
    ),
  listSuggestions: (token: string) => request<Suggestion[]>("/suggestions", token),
  dismissSuggestion: (token: string, id: string) =>
    request<void>(`/suggestions/${id}/dismiss`, token, { method: "POST" }),
  getHomeScreen: (token: string, clientTimezone?: string) => {
    const params = clientTimezone
      ? `?client_timezone=${encodeURIComponent(clientTimezone)}`
      : "";
    return request<HomeScreen>(`/home${params}`, token);
  },
};
