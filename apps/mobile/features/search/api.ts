import { request } from "@/lib/api/client";
import { withQuery } from "@/lib/api/path";
import type { Page, SearchResult } from "@/lib/api/types";

export const searchApi = {
  search: (
    token: string,
    q: string,
    limit = 20,
    init?: Pick<RequestInit, "signal">,
    cursor?: string,
  ) => {
    const path = withQuery("/search", { q, limit, cursor: cursor || undefined });
    return request<Page<SearchResult>>(path, token, init);
  },
};
