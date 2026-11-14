/**
 * A weather question about where the user is — the server's `is_local_weather_query`
 * (apps/api/app/modules/web_search/{geo_intent,weather}.py). The phone reads its location
 * for one as it does for a places ask: "What's the weather tomorrow?" read a saved place of
 * any age (review, 2026-11-09). docs/fixtures/geo_intent_cases.json holds the two to the
 * same answers. The server also leaves homework its turn reads to its subject; the phone
 * has no turn reading, so only the problems it can see on the line are left out here.
 */

/** Server `_WEATHER`: a forecast or the conditions, always live. */
const WEATHER = new RegExp(
  [
    String.raw`\b(?:(?:what(?:['\u2019]s|\s+is|\s+will\s+be)|how(?:['\u2019]s|\s+is))\s+the\s+`,
    String.raw`(?:weather|forecast|temperature)`,
    String.raw`|weather\s+(?:in|for|at|near|around|like|today|tomorrow|tonight|now|this\s+(?:week|weekend)`,
    String.raw`|forecast|report|update)`,
    String.raw`|(?:today|tomorrow|tonight)(?:['\u2019]s)?\s+(?:weather|forecast)`,
    String.raw`|(?:weather\s+)?forecast\s+(?:for|in|today|tomorrow|tonight|this)`,
    String.raw`|temperature\s+(?:outside|today|tomorrow|tonight|right\s+now|(?:in|at)\s+(?!(?:which|whom`,
    String.raw`|room|kelvin|celsius|fahrenheit|degrees?|the\s+same|absolute|this|that|a\s+(?:substance`,
    String.raw`|body|metal|liquid|gas))\b))`,
    String.raw`|(?:(?:will|is)\s+it|^(?:i\s+(?:want|need)\s+to\s+know|(?:can|could)\s+you\s+(?:tell\s+me|check)`,
    String.raw`|do\s+you\s+know|i\s+wonder|tell\s+me|check|find\s+out)\s+(?:if|whether)\s+it(?:\s+will`,
    String.raw`|['\u2019]ll|\s+is|['\u2019]s))\s+(?:going\s+to\s+|gonna\s+)?(?:rain|snow|storm)(?:ing)?`,
    String.raw`|(?:how|is\s+it)\s+(?:hot|cold|warm|humid)\s+(?:is\s+it\s+)?(?:outside|today|out|here))\b`,
  ].join(""),
  "i",
);

/** Server `WEATHER_NOT_A_FORECAST`: a figure of speech, a writing task, a science question. */
const NOT_A_FORECAST = new RegExp(
  [
    String.raw`\b(?:under\s+the\s+weather|weather\s+(?:the|this|that|a)\s+\w+`,
    String.raw`|fair[- ]weather|weather(?:ing)?\s+(?:out|through)`,
    String.raw`|(?:poem|story|song|essay|haiku|joke|sentence|paragraph)s?\s+(?:about|on)\s+(?:the\s+)?weather`,
    String.raw`|(?:mean(?:s|ing)?|definition|synonyms?|spell|spelling)\b.*\bweather`,
    String.raw`|weather\b.*\b(?:mean(?:s|ing)?|definition|synonyms?)`,
    String.raw`|weather\s+vs\.?\s+whether|whether\s+(?:or|vs)`,
    String.raw`|temperature(?![^.?!]*\b(?:today|tonight|tomorrow|now|this\s+(?:week|weekend))\b)`,
    String.raw`\s+(?:in\s+(?:kelvin|celsius|fahrenheit|centigrade)|at\s+which`,
    String.raw`|of\s+(?:a\s+|an\s+|the\s+)?(?:boiling|melting|freezing|ice|water|steam|sun|human\s+body`,
    String.raw`|body|object|substance|liquid|gas|flame|metal|core|surface\s+of))`,
    String.raw`|(?:weather|forecast|temperature|climate)(?:\s+[\w'\u2019]+){0,3}?\s+(?:(?:on|in|of|at)`,
    String.raw`\s+(?:the\s+)?(?:planet\s+)?(?:mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto`,
    String.raw`|moon|titan|europa|io|other\s+planets?|another\s+planet|exoplanets?)\b(?!\s*,)`,
    String.raw`|on\s+(?:the\s+)?sun\b))`,
  ].join(""),
  "i",
);

const STATED_TEMPERATURE = /\d\s*(?:°|degrees?\b)/i;
const TEMPERATURE_UNIT = /\b(?:fahrenheit|celsius|kelvin)\b/i;

/** Server `_MEASURED`: a quantity the question states ("2.50 L", "18 meters"). */
const MEASURED = new RegExp(
  [
    String.raw`\d(?:\.\d+)?\s*(?:mL|L|g|kg|mg|mol|atm|kPa|Pa|mmHg|torr|K|J|kJ|N|W|V|A|m|cm|km|m/s|Hz`,
    String.raw`|°\s*[CF]|(?:kilo|centi|milli)?met(?:er|re)s?|grams?|liters?|litres?|miles?|feet|foot)`,
    String.raw`(?![A-Za-z])`,
  ].join(""),
  "g",
);
const COORDINATES =
  /\b(?:points?|curve|graph|line|vertex|centre|center)\b[^.?!]{0,30}\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*\)/i;
const FUNCTION = /\b[a-zA-Z]\s*\(\s*[a-z]\s*\)\s*=/;

/** Server `_AROUND_THE_USER`: what is around the user, which no exercise asks for. */
const AROUND_THE_USER = new RegExp(
  [
    String.raw`\b(?:(?:near|close\s+to|around)\s+(?:me|here|my\s+(?:house|home|place|hotel|office|location))`,
    String.raw`|in\s+my\s+(?:area|neighbou?rhood|city|town)`,
    String.raw`|(?:from|at|for|to)\s+my\s+(?:current\s+)?location`,
    String.raw`|within\s+(?:walking\s+distance|\d+(?:\.\d+)?\s*[a-z]+\s+of\s+(?:me|here|my\s+\w+)))\b`,
  ].join(""),
  "i",
);

/** Server `_LOCATIONLESS_WEATHER`: the whole message asks the weather and names nothing. */
const LOCATIONLESS_WEATHER =
  /^\s*(?:what(?:'s|\s+is)\s+(?:the\s+)?weather(?:\s+like)?|weather(?:\s+(?:today|tomorrow|tonight|now))?|(?:the\s+)?forecast(?:\s+(?:today|tomorrow|tonight))?)\s*[?.!]*\s*$/i;

/** Server `_WEATHER_PLACE`: "weather in Paris" names its place; "weather this weekend" does not. */
const WEATHER_PLACE = new RegExp(
  [
    String.raw`\b(?:in|at|near|around|for)\s+`,
    String.raw`(?!(?:here|there|today|tomorrow|tonight|now|this|next|the\s+(?:weekend|week|day|morning`,
    String.raw`|afternoon|evening|night)|my\s+(?:area|location|city|town|place|neighbou?rhood))\b)`,
    String.raw`\p{L}`,
    String.raw`|\bon\s+(?:the\s+)?(?:mount|mt\.?|lake|isle\s+of)\s+\p{L}`,
  ].join(""),
  "iu",
);

/** Server `is_worked_problem`, as far as the line itself shows: measurements, a point, a function. */
function isWorkedProblem(text: string): boolean {
  return (text.match(MEASURED)?.length ?? 0) >= 2 || COORDINATES.test(text) || FUNCTION.test(text);
}

/** Server `is_weather_request`: a real forecast or conditions question. */
function isWeatherRequest(text: string): boolean {
  if (!WEATHER.test(text) || NOT_A_FORECAST.test(text)) return false;
  if (isWorkedProblem(text) && !AROUND_THE_USER.test(text)) return false;
  return !(STATED_TEMPERATURE.test(text) && TEMPERATURE_UNIT.test(text));
}

/** A weather question with no place named: answered for the user's location. */
export function isLocalWeatherQuery(text: string): boolean {
  if (LOCATIONLESS_WEATHER.test(text)) return true;
  return isWeatherRequest(text) && !WEATHER_PLACE.test(text);
}
