export type SearchSource = {
  title: string;
  url: string;
  snippet?: string;
};

const SOURCES_FENCE_RE = /```sources\s*\n([\s\S]*?)```/i;

function normalizeSourceRows(parsed: unknown): SearchSource[] {
  if (!Array.isArray(parsed)) return [];
  return parsed.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const row = item as Record<string, unknown>;
    const title = String(row.title ?? "").trim();
    const url = String(row.url ?? "").trim();
    if (!title && !url) return [];
    const snippetRaw = String(row.snippet ?? "").trim();
    const source: SearchSource = {
      title: title || url,
      url,
    };
    if (snippetRaw) source.snippet = snippetRaw;
    return [source];
  });
}

export function parseSearchSourcesJson(raw: string): SearchSource[] {
  try {
    return normalizeSourceRows(JSON.parse(raw));
  } catch {
    return [];
  }
}

export function parseSearchSources(content: string): SearchSource[] {
  const match = SOURCES_FENCE_RE.exec(content);
  if (!match) return [];
  return parseSearchSourcesJson(match[1].trim());
}

export function resolveSearchSources(
  content: string,
  attached?: SearchSource[] | null,
): SearchSource[] {
  if (attached && attached.length > 0) return attached;
  return parseSearchSources(content);
}

export function stripSearchSourcesFence(content: string): string {
  return content.replace(SOURCES_FENCE_RE, "").trimEnd();
}

export function hostnameFromUrl(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0] ?? url;
  }
}

export function faviconHost(url: string): string {
  const host = hostnameFromUrl(url);
  return host || "web";
}

export function faviconUrl(url: string): string {
  const host = hostnameFromUrl(url);
  if (!host) return "";
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=64`;
}
