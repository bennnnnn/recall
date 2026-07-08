export type SearchSource = {
  title: string;
  url: string;
  snippet?: string;
};

const SOURCES_FENCE_RE = /```sources\s*\n([\s\S]*?)```/gi;

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

function findTrailingSourcesJson(content: string): { sources: SearchSource[]; start: number } | null {
  const trimmed = content.trimEnd();
  for (let index = trimmed.lastIndexOf("["); index >= 0; index = trimmed.lastIndexOf("[", index - 1)) {
    const candidate = trimmed.slice(index);
    const sources = parseSearchSourcesJson(candidate);
    if (sources.length > 0) return { sources, start: index };
  }
  return null;
}

export function parseSearchSources(content: string): SearchSource[] {
  const fromFence = [...content.matchAll(SOURCES_FENCE_RE)].flatMap((match) =>
    parseSearchSourcesJson(match[1].trim()),
  );
  if (fromFence.length > 0) return fromFence;
  return findTrailingSourcesJson(content)?.sources ?? [];
}

export function resolveSearchSources(
  content: string,
  attached?: SearchSource[] | null,
): SearchSource[] {
  if (attached && attached.length > 0) return attached;
  return parseSearchSources(content);
}

/** Remove ```sources fences and trailing LLM-emitted source JSON from visible markdown. */
export function stripSearchSourcesFromContent(content: string): string {
  let text = content.replace(SOURCES_FENCE_RE, "");
  const trailing = findTrailingSourcesJson(text);
  if (trailing) {
    text = text.slice(0, trailing.start).trimEnd();
  }
  return text.trimEnd();
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
