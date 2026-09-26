import { request } from "@/lib/api/client";
import type { SearchResult } from "@/lib/api/types";

export const searchApi = {
  search: (
    token: string,
    q: string,
    limit = 20,
    init?: Pick<RequestInit, "signal">,
    offset = 0,
  ) => {
    const params = new URLSearchParams({ q, limit: String(limit), offset: String(offset) });
    return request<{ results: SearchResult[]; total: number }>(`/search?${params}`, token, init);
  },
};
