/**
 * The place a places question names for its venues — the server's `venue_place`
 * (apps/api/app/modules/web_search/venue_place.py), held to the same answers by
 * docs/fixtures/geo_intent_cases.json. "What are the best restaurants in Addis Ababa?"
 * names Addis Ababa, so the phone reads no GPS for it. A capital after "in" or "to" is
 * that place only in the clause that asks for the venues, after the ask and before any
 * purpose ("to get to Boston"), never after "from", and never a time (a month, a weekday,
 * a part of the day, a holiday). A sentence that opens with the place, or the user saying
 * where they are ("We're in Rome"), names it too.
 */

/** `word` in any case, as the server's `(?i:…)` group reads it: "to" is `[Tt][Oo]`. */
function anyCase(word: string): string {
  return Array.from(word, (letter) => `[${letter.toUpperCase()}${letter}]`).join("");
}

function anyCaseOf(words: readonly string[]): string {
  return words.map(anyCase).join("|");
}

/**
 * A capitalised name, never "I" or "A": only its capital is read as written. Its letters
 * are any script's, as Python's `\w` reads them ("Zürich", "cafés"): every pattern with one
 * carries the `u` flag.
 */
const WORD = String.raw`[\p{L}\p{N}_'\u2019.&-]`;
const NAME = String.raw`[A-Z](?![\s'\u2019])${WORD}*(?:\s+[A-Z]${WORD}*)*`;
const PLACED = new RegExp(
  String.raw`\b(?:${anyCaseOf(["in", "near", "around", "at", "to"])})\s+(?:the\s+)?(${NAME})`,
  "gu",
);
const PURPOSE_FREE = ["me", "my", "our", "your", "us", "the", "a", "an", "this", "that", "here", "there", "where"];
/** A purpose ends the venue's phrase: "to get to Boston". "To my hotel" does not. */
const PURPOSE = new RegExp(String.raw`\b${anyCase("to")}\s+(?!(?:${anyCaseOf(PURPOSE_FREE)})\b)[a-z]`);
const SENTENCE_END = /[.?!\n]/g;
const CLAUSE_END = /[.?!;,:\n]/g;
/** After a comma, a list that goes on ("restaurants, cafes and bars in Rome") is the same clause. */
const LIST_GOES_ON = /,\s*(?:[\p{L}\p{N}_'-]+\s+){0,3}?(?:and|or|&)\s/iuy;
const OPENS_WITH_PLACE = new RegExp(
  String.raw`^\s*(?:${anyCaseOf(["in", "at", "near", "around"])})\s+(?:the\s+)?(${NAME})`,
  "u",
);
const USER_IS_AT = new RegExp(
  String.raw`\b(?:I(?:'m|\u2019m|\s+am)|[Ww]e(?:'re|\u2019re|\s+are))\s+` +
    String.raw`(?:(?:now|currently|staying|based|living|here)\s+)?(?:${anyCaseOf(["in", "at"])})\s+(?:the\s+)?` +
    `(${NAME})`,
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

function placedAfter(text: string, start: number): string | null {
  let clause = text.slice(start, clauseEnd(text, start));
  const purpose = PURPOSE.exec(clause);
  if (purpose) clause = clause.slice(0, purpose.index);
  for (const found of clause.matchAll(PLACED)) {
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
    const place = placedAfter(text, askStart) ?? openingPlace(text, askStart);
    if (place) return place;
  }
  for (const found of text.matchAll(USER_IS_AT)) {
    const place = aPlace(found[1]!);
    if (place) return place;
  }
  return null;
}
