/**
 * The place that replaces the user's own in a places question — the server's `venue_place`
 * (apps/api/app/modules/web_search/venue_place.py), held to the same answers by
 * docs/fixtures/geo_intent_cases.json. Three shapes do: "in" and a name with no article in
 * the clause that asks for the venues ("the best restaurants in Addis Ababa"), a sentence
 * that opens with it ("In Rome, where should we eat?"), and the user saying where they are
 * ("We're in Rome"). "at", "near", "to" and "in the" are a venue or neighbourhood the user's
 * city still places, so the phone keeps reading its location; "in" and a time (a month, a
 * weekday, a part of the day, a holiday) names no place.
 */

/**
 * A capitalised name, never "I" or "A": only its capital is read as written. Its letters
 * are any script's, as Python's `\w` reads them ("Zürich", "cafés"): every pattern with one
 * carries the `u` flag.
 */
const WORD = String.raw`[\p{L}\p{N}_'\u2019.&-]`;
const NAME = String.raw`[A-Z](?![\s'\u2019])${WORD}*(?:\s+[A-Z]${WORD}*)*`;
/** "in" and a name with no article: the shape that replaces the user's place. */
const IN_NAME = String.raw`\b[Ii][Nn]\s+(?![Tt][Hh][Ee]\s)(${NAME})`;
const PLACED = new RegExp(IN_NAME, "gu");
const SENTENCE_END = /[.?!\n]/g;
const CLAUSE_END = /[.?!;,:\n]/g;
/** After a comma, a list that goes on ("restaurants, cafes and bars in Rome") is the same clause. */
const LIST_GOES_ON = /,\s*(?:[\p{L}\p{N}_'-]+\s+){0,3}?(?:and|or|&)\s/iuy;
const OPENS_WITH_PLACE = new RegExp(String.raw`^\s*${IN_NAME}`, "u");
const USER_IS_IN = new RegExp(
  String.raw`\b(?:I(?:'m|\u2019m|\s+am)|[Ww]e(?:'re|\u2019re|\s+are))\s+` +
    String.raw`(?:(?:now|currently|staying|based|living|here)\s+)?` +
    IN_NAME,
  "gu",
);
/** Times written with a capital: months, weekdays, parts of the day, holidays. */
const TIME = new RegExp(
  [
    "^(?:January|February|March|April|May|June|July|August|September|October|November",
    "|December|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Morning|Afternoon",
    "|Evening|Night|Tonight|Today|Tomorrow|Weekend|Christmas|Easter|Thanksgiving|Halloween",
    String.raw`|Ramadan|Eid|Diwali|Hanukkah|Passover|Lent|Valentine|New\s+Year|Meskel|Timkat|Genna)\b`,
  ].join(""),
);

function aPlace(name: string): string | null {
  return TIME.test(name) ? null : name.trim();
}

/** Where the clause holding `start` ends: its punctuation, past a list that goes on. */
function clauseEnd(text: string, start: number): number {
  CLAUSE_END.lastIndex = start;
  let end = CLAUSE_END.exec(text);
  while (end && end[0] === ",") {
    LIST_GOES_ON.lastIndex = end.index;
    if (!LIST_GOES_ON.test(text)) break;
    CLAUSE_END.lastIndex = end.index + 1;
    end = CLAUSE_END.exec(text);
  }
  return end ? end.index : text.length;
}

/** The place the ask's own clause names, before or after the ask. */
function inClause(text: string, ask: number): string | null {
  let start = 0;
  CLAUSE_END.lastIndex = 0;
  for (let found = CLAUSE_END.exec(text); found && found.index < ask; found = CLAUSE_END.exec(text)) {
    start = found.index + 1;
  }
  for (const found of text.slice(start, clauseEnd(text, ask)).matchAll(PLACED)) {
    const place = aPlace(found[1]!);
    if (place) return place;
  }
  return null;
}

function openingPlace(text: string, start: number): string | null {
  let sentenceStart = 0;
  SENTENCE_END.lastIndex = 0;
  for (let found = SENTENCE_END.exec(text); found && found.index < start; found = SENTENCE_END.exec(text)) {
    sentenceStart = found.index + 1;
  }
  const found = OPENS_WITH_PLACE.exec(text.slice(sentenceStart, start));
  return found ? aPlace(found[1]!) : null;
}

/** The place a places question names for its venues, or null: the user's own place. */
export function venuePlace(text: string, askStart: number | null): string | null {
  if (askStart !== null) {
    const place = inClause(text, askStart) ?? openingPlace(text, askStart);
    if (place) return place;
  }
  for (const found of text.matchAll(USER_IS_IN)) {
    const place = aPlace(found[1]!);
    if (place) return place;
  }
  return null;
}
