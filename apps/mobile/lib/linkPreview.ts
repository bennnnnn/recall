import { getApiUrl } from "@/lib/config";
import { getToken } from "@/lib/auth";

export type LinkPreview = {
  url: string;
  title: string | null;
  description: string | null;
  domain: string;
};

const cache = new Map<string, LinkPreview>();

export async function fetchLinkPreview(url: string): Promise<LinkPreview> {
  const cached = cache.get(url);
  if (cached) return cached;

  const token = await getToken();
  const api = `${getApiUrl()}/link-preview?url=${encodeURIComponent(url)}`;
  const res = await fetch(api, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("preview failed");
  const data = (await res.json()) as LinkPreview;
  cache.set(url, data);
  return data;
}
