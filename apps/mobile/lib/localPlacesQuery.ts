/**
 * Universal geo intent — mirrors backend `is_geo_query` / `is_places_list_query`.
 * Detects *how* the user asks (proximity, distance), never *what* venue type.
 */

const NEARBY_INTENT =
  /\b(near\s+me|nearby|around\s+here|in(?:\s+this)?\s+town|close\s+(?:by|to\s+me)|(?:the\s+)?(?:nearest|closest))\b/i;

const NON_GEOGRAPHIC_NEAREST =
  /\b(?:nearest|closest)\b.+\b(number|numbers|integer|prime|multiple|match|deadline|star|planet|galaxy|sun|moon|approach|analogy|synonym|equivalent|friend|relative|cousin|neighbor|neighbour|guess|approximation|solution|competitor|rival)\b/i;

const BEST_NEAR = /\bbest\b.+\b(?:in|near|around|by)\b/i;

const IMPLICIT_LOCAL =
  /\b(where\s+(?:should|can|do)\s+(?:I|we)\s+(?:eat|get|find|go|stay|park)|where\s+to\s+(?:eat|go|get|stay|park)|what(?:'s| is)\s+(?:good|open)\s+(?:around|near|nearby))\b/i;

const DISTANCE_INTENT =
  /\b(how\s+far|how\s+many\s+(?:miles|kilometers|kilometres|km|minutes|mins)|(?:walking|driving|drive|travel|commute)\s+(?:distance|time)|distance\s+(?:to|from)|how\s+long\s+(?:to\s+get|does\s+it\s+take|is\s+the\s+(?:drive|trip|walk))|(?:miles|km|kilometers?|kilometres?|minutes?)\s+(?:away|from\s+(?:me|here))|directions?\s+to)\b/i;

const FROM_USER =
  /\b(?:from\s+(?:me|here|my\s+(?:location|place))|to\s+me|where\s+i\s+am)\b/i;

const DISTANCE_BETWEEN = /\bdistance\b.+\bbetween\b/i;

const AMBIGUOUS_NEARBY_SUBJECT =
  /\b(house|houses|home|homes|property|properties|building|buildings|apartment|apartments|condo|condos|flat|flats|unit|units)\b/i;

const QUALIFIED_NEARBY =
  /\b(for\s+sale|to\s+(?:buy|rent|lease)|for\s+rent|rentals?|buying|leasing|open\s+(?:now|today)|24\s*hours?|near\s+\d|at\s+\d|from\s+\d|\d+\s+\w+\s+(?:st|street|ave|avenue|rd|road|blvd|dr|drive|way|ln|lane)\b)\b/i;

const PROXIMITY_PHRASES = [
  /\bnear\s+me\b/i,
  /\bnearby\b/i,
  /\baround\s+here\b/i,
  /\bin(?:\s+this)?\s+town\b/i,
  /\bclose\s+(?:by|to\s+me)\b/i,
  /\b(?:the\s+)?(?:nearest|closest)\b/i,
  /\bbest\b/i,
];

/** Mirrors backend `is_location_question` — needs a fresh device fix. */
const LOCATION_QUESTION =
  /^\s*(?:where am i(?:\s+(?:at|right\s+now|right\s+nwo|now|currently))?\??|what(?:'s| is) my (?:current\s+)?location\??|where(?:'s| is) my (?:current\s+)?location\??|where(?:'re| are) we(?:\s+(?:right\s+now|now|currently))?\??|my (?:current\s+)?location\??|location\??)\s*[.!?]*\s*$/i;

function subjectWithoutProximity(cleaned: string): string {
  let subject = cleaned.trim();
  for (const pattern of PROXIMITY_PHRASES) {
    subject = subject.replace(pattern, " ");
  }
  return subject.replace(/\s+/g, " ").trim().replace(/[ ?.!]+$/, "");
}

export function isLocationQuestion(text: string): boolean {
  return LOCATION_QUESTION.test(text.trim());
}

export function isProximityQuery(text: string): boolean {
  const cleaned = text.trim();
  if (!cleaned) return false;
  if (NON_GEOGRAPHIC_NEAREST.test(cleaned)) return false;
  if (NEARBY_INTENT.test(cleaned)) return true;
  if (IMPLICIT_LOCAL.test(cleaned)) return true;
  return BEST_NEAR.test(cleaned) && cleaned.includes("?");
}

export function isDistanceQuery(text: string): boolean {
  const cleaned = text.trim();
  if (!cleaned || !DISTANCE_INTENT.test(cleaned)) return false;
  if (DISTANCE_BETWEEN.test(cleaned) && !FROM_USER.test(cleaned)) return false;
  return true;
}

/** Needs user GPS / profile location — nearby, distance, or "where am I". */
export function isGeoQuery(text: string): boolean {
  return isProximityQuery(text) || isDistanceQuery(text) || isLocationQuestion(text);
}

/** Native ```places card — find venues, not mileage-only. */
export function isPlacesListQuery(text: string): boolean {
  if (isAmbiguousLocalPlacesQuery(text)) return false;
  return isProximityQuery(text);
}

/** @deprecated Use isGeoQuery — kept for call-site clarity. */
export const isLocalPlacesQuery = isGeoQuery;

export function isAmbiguousLocalPlacesQuery(text: string): boolean {
  const cleaned = text.trim();
  if (!isProximityQuery(cleaned)) return false;
  if (QUALIFIED_NEARBY.test(cleaned)) return false;
  const subject = subjectWithoutProximity(cleaned);
  if (!subject) return false;
  return AMBIGUOUS_NEARBY_SUBJECT.test(subject);
}
