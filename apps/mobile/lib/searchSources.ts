import {
  collectClosedFenceBodies,
  mapUnlabeledClosedFences,
  stripClosedLangFence,
} from "@/lib/mdFenceScan";

export type SearchSource = {
  title: string;
  url: string;
  snippet?: string;
};

const SOURCES_LABEL_RE = /(?:\*\*)?sources(?:\*\*)?\s*:?\s*$/i;

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
  const text = raw.trim();
  try {
    return normalizeSourceRows(JSON.parse(text));
  } catch {
    return [];
  }
}

export function parseSearchSources(content: string): SearchSource[] {
  const fromFence = collectClosedFenceBodies(content, "sources").flatMap((body) =>
    parseSearchSourcesJson(body),
  );
  if (fromFence.length > 0) return fromFence;

  const fromBare: SearchSource[] = [];
  mapUnlabeledClosedFences(content, (body, original) => {
    fromBare.push(...parseSearchSourcesJson(body));
    return original;
  });
  return fromBare;
}

export function resolveSearchSources(
  content: string,
  attached?: SearchSource[] | null,
): SearchSource[] {
  if (attached && attached.length > 0) return attached;
  return parseSearchSources(content);
}

/** Remove ```sources fences and unlabeled source-JSON fences from visible markdown. */
export function stripSearchSourcesFromContent(content: string): string {
  let text = stripClosedLangFence(content, "sources");
  text = mapUnlabeledClosedFences(text, (body, original) =>
    parseSearchSourcesJson(body).length > 0 ? "" : original,
  );
  text = text.replace(SOURCES_LABEL_RE, "").trimEnd();
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
