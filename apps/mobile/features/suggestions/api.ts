import { request } from "@/lib/api/client";
import type { Suggestion } from "@/lib/api/types";

export const suggestionsApi = {
  listSuggestions: (token: string) => request<Suggestion[]>("/suggestions", token),
  dismissSuggestion: (token: string, id: string) =>
    request<void>(`/suggestions/${id}/dismiss`, token, { method: "POST" }),
};
