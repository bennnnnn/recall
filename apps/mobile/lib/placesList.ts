export type PlaceItem = {
  name: string;
  url: string;
  note?: string;
  address?: string;
  price?: string;
};

const PLACES_FENCE_RE = /```places\s*\n([\s\S]*?)```/gi;
const PLACES_JSON_FENCE_RE = /```json\s*\n([\s\S]*?)```/gi;
const PRICE_IN_NOTE_RE = /\(\s*\$+\s*\)/;
const NUMBERED_LINE_RE = /^\s*\d+\.\s+/;
const SECTION_HEADING_RE = /^\s*#{1,6}\s+/;

type ParsedVenueLine = {
  name: string;
  rawUrl?: string;
  note?: string;
  address?: string;
  price?: string;
};

function parseVenueListLine(line: string): ParsedVenueLine | null {
  let rest = line.replace(/^\s*\d+\.\s+/, "").trim();
  if (!rest) return null;

  let name = "";
  let rawUrl = "";
  let note = "";

  const boldLink = rest.match(/^\*\*\[([^\]]+)\]\(([^)]+)\)\*\*(.*)$/);
  const plainLink = rest.match(/^\[([^\]]+)\]\(([^)]+)\)(.*)$/);
  const boldName = rest.match(/^\*\*([^*]+)\*\*(.*)$/);

  if (boldLink) {
    name = boldLink[1].trim();
    rawUrl = boldLink[2].trim();
    note = boldLink[3].replace(/^[—–-]\s*/, "").trim();
  } else if (plainLink) {
    name = plainLink[1].trim();
    rawUrl = plainLink[2].trim();
    note = plainLink[3].replace(/^[—–-]\s*/, "").trim();
  } else if (boldName) {
    name = boldName[1].trim();
    note = boldName[2].replace(/^[—–-]\s*/, "").trim();
  } else {
    const parts = rest.split(/\s[—–-]\s/);
    name = (parts[0] ?? "").trim();
    note = parts.slice(1).join(" — ").trim();
  }

  if (!name) return null;

  let price = "";
  const priceMatch = note.match(PRICE_IN_NOTE_RE);
  if (priceMatch) {
    price = priceMatch[0].replace(/[()]/g, "").trim();
    note = note.replace(PRICE_IN_NOTE_RE, "").replace(/\s+/g, " ").trim();
  }

  const parsed: ParsedVenueLine = { name };
  if (rawUrl) parsed.rawUrl = rawUrl;
  if (note) parsed.note = note;
  if (price) parsed.price = price;
  return parsed;
}

function rowToPlace(row: ParsedVenueLine): PlaceItem {
  const place: PlaceItem = {
    name: row.name,
    url: resolvePlaceLinkUrl({
      name: row.name,
      url: row.rawUrl ?? "",
      address: row.address ?? "",
    }),
  };
  if (row.note) place.note = row.note;
  if (row.address) place.address = row.address;
  if (row.price) place.price = row.price;
  return place;
}

/** Pull venue rows from numbered markdown lists (legacy model output). */
export function extractPlacesFromMarkdownList(content: string): PlaceItem[] {
  const lines = content.split("\n");
  const places: PlaceItem[] = [];
  let run: ParsedVenueLine[] = [];

  const flush = () => {
    if (run.length >= 2) {
      places.push(...run.map(rowToPlace));
    }
    run = [];
  };

  for (const line of lines) {
    if (NUMBERED_LINE_RE.test(line)) {
      const parsed = parseVenueListLine(line);
      if (parsed) {
        run.push(parsed);
        continue;
      }
    }
    if (SECTION_HEADING_RE.test(line.trim())) {
      continue;
    }
    flush();
  }
  flush();
  return places;
}

export function parseAllPlacesFences(content: string): PlaceItem[] {
  const places: PlaceItem[] = [];
  for (const match of content.matchAll(PLACES_FENCE_RE)) {
    places.push(...parsePlacesJson(match[1]?.trim() ?? ""));
  }
  return places;
}

/** Hide ```places / ```json venue blocks from markdown (incl. while streaming). */
export function stripGeoFenceBlocks(text: string): string {
  return text
    .replace(/```(?:places|json)\s*\n[\s\S]*?(?:```|$)/gi, "")
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd();
}

/** Unified venue list — ```places fences, or ```json arrays the model mis-tagged. */
export function resolvePlaces(content: string): PlaceItem[] {
  const fromPlaces = parseAllPlacesFences(content);
  if (fromPlaces.length > 0) return fromPlaces;
  return parsePlacesJsonFences(content);
}

/** Remove places/json venue fences from prose (leave markdown body intact). */
export function stripPlacesContent(content: string, places: PlaceItem[]): string {
  if (places.length === 0) return content;
  let stripped = content.replace(PLACES_FENCE_RE, "");
  if (stripped.includes("```json")) {
    stripped = stripped.replace(PLACES_JSON_FENCE_RE, (block, raw: string) => {
      try {
        return looksLikePlacesArray(JSON.parse(String(raw).trim())) ? "" : block;
      } catch {
        return block;
      }
    });
  }
  return stripped.replace(/\n{3,}/g, "\n\n").trimEnd();
}

/** Google Maps search/deep link — opens Maps on iOS and Android. */
export function googleMapsSearchUrl(query: string): string {
  const q = query.trim();
  if (!q) return "";
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
}

export function isGenericSearchUrl(url: string): boolean {
  const trimmed = url.trim();
  if (!trimmed) return true;
  try {
    const u = new URL(trimmed);
    const host = u.hostname.replace(/^www\./, "").toLowerCase();
    const path = u.pathname.toLowerCase();
    if (host === "yelp.com" && path.startsWith("/search")) return true;
    // Require an exact google.com host or a real subdomain (not evilgoogle.com).
    if (
      (host === "google.com" || host.endsWith(".google.com")) &&
      path.includes("/search")
    ) {
      return true;
    }
    if (host === "bing.com" && path.includes("/search")) return true;
    if (host === "duckduckgo.com") return true;
    return false;
  } catch {
    return true;
  }
}

function mapsQueryForPlace(name: string, address: string): string {
  const n = name.trim();
  const a = address.trim();
  if (!a) return n;
  if (!n) return a;
  const nameRe = new RegExp(`\\b${n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
  if (nameRe.test(a)) return a;
  return `${n}, ${a}`;
}

/** Open Maps for the venue — prefer a direct venue URL when present. */
export function resolvePlaceLinkUrl(place: Pick<PlaceItem, "name" | "url" | "address">): string {
  const raw = place.url?.trim() ?? "";
  if (raw && !isGenericSearchUrl(raw)) {
    return raw;
  }
  const name = place.name.trim();
  const address = place.address?.trim() ?? "";
  return googleMapsSearchUrl(mapsQueryForPlace(name, address));
}

function looksLikePlacesArray(parsed: unknown): boolean {
  if (!Array.isArray(parsed) || parsed.length === 0) return false;
  return parsed.every((item) => {
    if (!item || typeof item !== "object") return false;
    const row = item as Record<string, unknown>;
    return typeof row.name === "string" && row.name.trim().length > 0;
  });
}

function parsePlacesJsonFences(content: string): PlaceItem[] {
  const places: PlaceItem[] = [];
  for (const match of content.matchAll(PLACES_JSON_FENCE_RE)) {
    const raw = match[1]?.trim() ?? "";
    try {
      const parsed = JSON.parse(raw);
      if (looksLikePlacesArray(parsed)) {
        places.push(...normalizePlaceRows(parsed));
      }
    } catch {
      // ignore non-JSON fences
    }
  }
  return places;
}

function normalizePlaceRows(parsed: unknown): PlaceItem[] {
  if (!Array.isArray(parsed)) return [];
  return parsed.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const row = item as Record<string, unknown>;
    const name = String(row.name ?? "").trim();
    const rawUrl = String(row.url ?? "").trim();
    const note = String(row.note ?? row.snippet ?? "").trim();
    const address = String(row.address ?? row.location ?? "").trim();
    const price = String(row.price ?? row.price_tier ?? "").trim();
    if (!name) return [];

    const place: PlaceItem = {
      name,
      url: resolvePlaceLinkUrl({ name, url: rawUrl, address }),
    };
    if (note) place.note = note;
    if (address) place.address = address;
    if (price) place.price = price;
    return [place];
  });
}

export function parsePlacesJson(raw: string): PlaceItem[] {
  try {
    return normalizePlaceRows(JSON.parse(raw));
  } catch {
    return [];
  }
}

export function parsePlacesFence(content: string): PlaceItem[] {
  return parseAllPlacesFences(content);
}

export function stripPlacesFence(content: string): string {
  return content.replace(PLACES_FENCE_RE, "").trimEnd();
}

/** Fix model output where markdown links use $url$ instead of (url). */
export function repairBrokenMarkdownLinks(content: string): string {
  return content.replace(/\[([^\]\n]+)\]\$([^$\n]+?)\$/g, "[$1]($2)");
}
