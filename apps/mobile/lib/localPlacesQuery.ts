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

// A walk or drive across, around or along something ("walk across the Brooklyn
// Bridge") takes that thing's length, wherever the user is. "Walk over to
// Sara's" is still a trip from the user.
const ALONG_A_PLACE = String.raw`(?!\s+(?:(?:across|around|over|through|along)\b(?!\s+to\b)|the\s+length\s+of\b))`;

// "How far did it go in that time?" asks how far something moved: the car of
// the problem before it, a ball, a friend. A trip from the user is "how far is".
const HOW_FAR_IT_MOVED = [
  String.raw`(?!\s+(?:does|did|do|will|would|can|could|has|had|have)\s+`,
  String.raw`(?:it|she|he|they|we|you|(?:the|this|that)\s+[a-z]+)\s+`,
  String.raw`(?:go|goes|gone|went|get|got|travel\w*|fall\w*|fell|move\w*|fly|flies|flew|flown`,
  String.raw`|roll\w*|slide|slid|drift\w*|run|ran|swim|swam|jump\w*|cover\w*)\b)`,
].join("");

/** Keep in sync with apps/api/app/modules/web_search/patterns.py `_DISTANCE_INTENT`. */
const DISTANCE_INTENT = new RegExp(
  [
    String.raw`\b(how\s+far${HOW_FAR_IT_MOVED}|how\s+many\s+(?:miles|kilometers|kilometres|km|minutes|mins)`,
    String.raw`|(?:walking|driving|drive|travel|commute)\s+(?:distance|time)|distance\s+(?:to|from)`,
    String.raw`|how\s+long\s+(?:to\s+get`,
    String.raw`|does\s+it\s+take\s+to\s+(?:get|reach|arrive|(?:drive|walk)${ALONG_A_PLACE})`,
    String.raw`|is\s+the\s+(?:trip|(?:drive|walk)${ALONG_A_PLACE}))`,
    String.raw`|(?:miles|km|kilometers?|kilometres?|minutes?)\s+(?:away|from\s+(?:me|here))`,
    String.raw`|directions?\s+to)\b`,
  ].join(""),
  "i",
);

const CLOCK_TIME = String.raw`(?:\d{1,2}(?::[0-5]\d)?\s*[ap]\.?m\b\.?|\d{1,2}:[0-5]\d\b|noon\b|midnight\b)`;

/**
 * "A bus leaves at 7:15am and arrives at 9:40am. How long is the trip?" is a
 * sum over the two times it states. "Arrive by 7pm" is a deadline and stays a
 * trip from the user.
 * Keep in sync with apps/api/app/modules/web_search/patterns.py `_TIMETABLE`.
 */
const TIMETABLE = new RegExp(
  [
    String.raw`\b(?:leaves?|left|leaving|departs?|departed|departing|sets?\s+off)\b`,
    String.raw`(?:\s+\S+){0,3}?\s+${CLOCK_TIME}`,
    String.raw`.{0,80}?`,
    String.raw`\b(?:arrives?|arrived|arriving|reaches|reached|lands?|landed|gets\s+in|got\s+in)\b`,
    String.raw`(?:\s+(?!by\b)\S+){0,3}?\s+${CLOCK_TIME}`,
  ].join(""),
  "i",
);

/**
 * "How many miles is a 5k?" and "how many minutes in an hour?" convert a stated
 * amount. "How many miles is it to Hawassa?" is still a trip from the user.
 * Keep in sync with apps/api/app/modules/web_search/patterns.py `_UNIT_CONVERSION`.
 */
const UNIT_CONVERSION = new RegExp(
  [
    String.raw`\bhow\s+many\s+(?:miles|kilometers|kilometres|km|minutes|mins)\s+`,
    String.raw`(?:(?:is|are)(?:\s+there)?(?:\s+in)?|in|makes?|equals?)\s+`,
    String.raw`(?:(?:a|an|one)\s+)?`,
    String.raw`(?:\d[\d,.]*\s*(?:k|km|kilomet(?:er|re)s?|mi|miles?|m|meters?|metres?|ft|feet|yards?`,
    String.raw`|h|hrs?|hours?|days?|weeks?|laps?|steps?)`,
    String.raw`|(?:half[\s-]?)?marathons?|kilomet(?:er|re)s?|miles?|hours?|days?|weeks?|months?`,
    String.raw`|years?|laps?)\b`,
  ].join(""),
  "i",
);

/** Keep in sync with apps/api/app/modules/web_search/patterns.py `_MOTION_HOMEWORK`. */
const MOTION_HOMEWORK = new RegExp(
  [
    String.raw`\b(?:accelerat(?:e|es|ed|ing|ion)|decelerat(?:e|es|ed|ing|ion)|from\s+rest|kinematics`,
    String.raw`|projectile|free\s*falls?|pivot|fulcrum|lever|torque`,
    String.raw`|constant\s+(?:rate|acceleration|speed|velocity)|metres?\s+per\s+second|meters?\s+per\s+second`,
    // "A train leaves at 9am and travels at 60 km/h. How far has it gone?"
    String.raw`|km\s+(?:per|an)\s+hour|miles\s+(?:per|an)\s+hour|travel(?:s|ed|led)?\s+at|average\s+speed`,
    // "A ball is kicked at 40° ... how far does it go?" is a launch, not a trip.
    String.raw`|thrown|kicked(?!\s+off)|(?:above|below)\s+the\s+(?:horizontal|ground)`,
    // "How far is the image from the lens?" is optics, not the user's location.
    String.raw`|lens(?:es)?|mirror|focal|echo(?:es)?|pendulum|wavelength|refract\w*)\b`,
    // A speed unit may sit right on its number: "90km/h", "5m/s".
    String.raw`|(?<![A-Za-z])(?:m\s*\/\s*s|km\s*\/\s*h|kph|mph)\b`,
    String.raw`|\d\s*(?:cm|mm)\b|\d\s*°`,
  ].join(""),
  "i",
);

const FROM_USER =
  /\b(?:from\s+(?:me|here|my\s+(?:location|place))|to\s+me|where\s+i\s+am)\b/i;

const DISTANCE_BETWEEN = /\bdistance\b.+\bbetween\b/i;

// “distance from A to B” names its origin and does not need the device's
// location. This also keeps geometry questions such as “distance from center
// to chord” out of the GPS shortcut. Only an explicit user-relative origin
// (“from me/here/my location”) may use device geo.
const FIXED_DISTANCE_FROM = /\bdistance\s+from\b/i;

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

const LOCATION_ASK_MAX_LEN = 80;
const LOCATION_ASK_FOLDED = new Set([
  "whereami",
  "whereamiat",
  "whereamirightnow",
  "whereamirightnwo",
  "whereaminow",
  "whereamicurently",
  "whatsmylocation",
  "whatismylocation",
  "whatsmycurrentlocation",
  "whatismycurrentlocation",
  "wherismylocation",
  "wheresmylocation",
  "whereismylocation",
  "wherearewe",
  "wherearewenow",
  "wherearewerightnow",
  "wherearewecurently",
  "mylocation",
  "mycurrentlocation",
  "location",
]);

/** Letters only, consecutive duplicates collapsed — "Where am iI" → whereami. */
function foldLocationAsk(text: string): string {
  if (text.length > LOCATION_ASK_MAX_LEN) return "";
  let out = "";
  let prev = "";
  const lower = text.toLowerCase();
  for (let i = 0; i < lower.length; i++) {
    const ch = lower[i]!;
    if (ch < "a" || ch > "z") continue;
    if (ch !== prev) {
      out += ch;
      prev = ch;
    }
  }
  return out;
}

function subjectWithoutProximity(cleaned: string): string {
  let subject = cleaned.trim();
  for (const pattern of PROXIMITY_PHRASES) {
    subject = subject.replace(pattern, " ");
  }
  return subject.replace(/\s+/g, " ").trim().replace(/[ ?.!]+$/, "");
}

export function isLocationQuestion(text: string): boolean {
  const cleaned = text.trim();
  if (!cleaned) return false;
  if (LOCATION_QUESTION.test(cleaned)) return true;
  return LOCATION_ASK_FOLDED.has(foldLocationAsk(cleaned));
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
  if (MOTION_HOMEWORK.test(cleaned)) return false;
  if (TIMETABLE.test(cleaned) || UNIT_CONVERSION.test(cleaned)) return false;
  if (DISTANCE_BETWEEN.test(cleaned) && !FROM_USER.test(cleaned)) return false;
  if (FIXED_DISTANCE_FROM.test(cleaned) && !FROM_USER.test(cleaned)) return false;
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

export function isAmbiguousLocalPlacesQuery(text: string): boolean {
  const cleaned = text.trim();
  if (!isProximityQuery(cleaned)) return false;
  if (QUALIFIED_NEARBY.test(cleaned)) return false;
  const subject = subjectWithoutProximity(cleaned);
  if (!subject) return false;
  return AMBIGUOUS_NEARBY_SUBJECT.test(subject);
}
