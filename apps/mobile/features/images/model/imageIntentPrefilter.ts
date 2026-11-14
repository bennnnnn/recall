/**
 * Whether a composer send might be a picture or a photo lookup, so the server is
 * worth asking (`POST /images/intent`). Only the server reads image intent: this
 * decides nothing but the round trip. A false positive costs one request; a miss
 * would send a picture request as plain chat, so the words come from the server's
 * own lists (apps/api/app/modules/images/gen_intent_words.py, lookup_intent.py and
 * intent.py), and the test runs every case the server draws or looks up. They count as
 * whole words in the shape of a request: a picture word inside another word or named in
 * passing ("photosynthesis", "Where is the image?") asked for nothing (2026-11-08 test).
 */

import {
  IMAGE_GEN_FAILED_ASSISTANT_ID,
  IMAGE_GEN_PENDING_ASSISTANT_ID,
} from "@/features/images/model/imageGenMessages";

type Row = { id: string; role: string; content: string };

/**
 * The English words the server's readers need, as whole words: a word inside another
 * ("photo" in "photosynthesis") is not one. A drawing verb asks wherever it stands.
 */
const DRAW_WORDS = new Set([
  "draw", "draws", "drawing", "drawings", "paint", "paints", "painting", "paintings",
  "illustrate", "illustrated", "illustration", "illustrations", "sketch",
]);
/** Picture nouns: asked about only as something requested (`asksForPicture`). */
const PICTURE_NOUNS = new Set([
  "image", "images", "picture", "pictures", "pic", "pics", "photo", "photos", "photograph",
  "photographs", "artwork", "artworks", "portrait", "portraits",
]);
/** "Create a cat", "make a logo": the server reads these only at the head of a short message. */
const MAKE_VERBS = new Set(["create", "generate", "make", "design", "render", "produce"]);
/** Verbs a picture noun is requested with: "send me a photo", "can I see her picture". */
const REQUEST_VERBS = new Set([
  ...MAKE_VERBS, ...DRAW_WORDS, "show", "see", "find", "get", "give", "send", "pull", "bring", "want",
  "need", "have", "got", "search",
]);
/** Words before a request's verb that ask politely: "can you show me", "please draw". */
const LEAD_WORDS = new Set(["please", "pls", "plz", "kindly", "just", "now", "also", "and", "then", "so", "ok",
  "okay", "hey", "can", "could", "would", "will", "you", "u"]);
/** "can I see X", "may we see X" (lookup_intent's see leads). */
const SEE_ASKS = new Set(["can", "could", "may"]);
/** "I want to see X", "I'd like to see X". */
const SEE_WANTS = new Set(["want", "like", "love"]);
/** A sentence these open asks about a picture ("Where is the image?"), not for one. */
const QUESTION_WORDS = new Set(["how", "what", "where", "when", "why", "which", "who", "whose", "whom"]);
/** "make it …", "make this …" (gen_intent_words.REVISION_PRONOUNS). */
const REVISION_PRONOUNS = new Set(["it", "them", "this", "that"]);
/** The server reads "create a cat" only in a message this short (gen_intent.extract_image_gen_prompt). */
const SHORT_REQUEST = 80;
/**
 * The same in the app's other languages (gen_intent_languages.py): the server draws there
 * only "draw me" ("dibújame", "zeichne mir", "bana … çiz", "ድመት ሳልልኝ") and "create a
 * picture of" ("erstelle ein Bild von", "crea una ilustración de"), so these are its draw
 * verbs and picture nouns. German "mal"/"male" count only before "mir"/"uns": alone they
 * are "once" and "bad" ("Erklär mal …", "Me siento mal").
 */
const OTHER_LANGUAGE_WORDS = new RegExp(
  "(?:^|[^a-z0-9_])(?:" +
    "dibuj|dibúj|pínt|pintame|pintas|pintar|ilustrac|ilustraç|imagen|imagem|dessin|peins|peignez|peindre|illustr|" +
    "zeichn|male?\\s+(?:mir|uns)(?![a-zäöüß])|malen|bild(?![a-zäöüß])|" +
    "disegn|dipin|immagin|desenh|çiz|resm|görsel|" +
    "нарис|изобра|картинк|рисун|иллюстр|" +
    "ሳልልኝ|ሣልልኝ|ሳይልኝ|ሣይልኝ|ሳሉልኝ|ሣሉልኝ|ምስል|ስዕል|ሥዕል|ስእል)",
);
/** With an image attached, these start an edit of it ("crop it", "turn it into…", "make it blue"). */
const EDIT_WORDS = /(?:^|[^a-z0-9_])(?:edit|change|remove|replace|recolor|crop|transform|turn|make)/;
/** "do it" after a picture request: the server reads one only in a line this short. */
const SHORT_LINE = 40;
const CLOSING_PUNCTUATION = /[.!?]+$/;

/** The words of each sentence, lowercased; a word keeps its apostrophe ("i'd"). */
function sentences(folded: string): string[][] {
  return folded
    .split(/[.!?\n:;]+/)
    .map((sentence) => sentence.match(/[\p{L}\p{N}_']+/gu) ?? [])
    .filter((words) => words.length > 0);
}

/** The sentence's first word past its polite leads: "can you please show me" is "show". */
function headWord(words: readonly string[]): string | undefined {
  return words.find((word) => !LEAD_WORDS.has(word));
}

/** A sentence that asks a question opens with one of these: "where's" is "where". */
function opensQuestion(words: readonly string[]): boolean {
  return QUESTION_WORDS.has(words[0].replace(/'.*$/, ""));
}

/** "of", and the French "de"/"d'un" the server reads after "une image". */
function isOf(word: string | undefined): boolean {
  return word === "of" || word === "de" || Boolean(word?.startsWith("d'"));
}

/**
 * A picture noun asked for: "a photo of X", one that closes a sentence ("cat pic", "photo
 * please"; not "Where is the image?"), or one a request verb in its sentence asks for
 * ("show me his photo").
 */
function asksForPicture(words: readonly string[]): boolean {
  let end = words.length;
  while (end > 1 && LEAD_WORDS.has(words[end - 1])) end -= 1;
  return words.some((word, i) => {
    if (!PICTURE_NOUNS.has(word)) return false;
    if (isOf(words[i + 1])) return true;
    if (i === end - 1 && !opensQuestion(words)) return true;
    return words.some((other) => REQUEST_VERBS.has(other));
  });
}

/** "see" as the lookup asks it: "let me see", "can I see", "I'd like to see"; not "I see". */
function asksToSeeAt(words: readonly string[], i: number): boolean {
  const before = words[i - 1];
  if (before === "me" || before === "lemme" || before === "wanna") return true;
  if (before === "i" || before === "we") return SEE_ASKS.has(words[i - 2] ?? "");
  return before === "to" && SEE_WANTS.has(words[i - 2] ?? "");
}

/** The photo lookup's asks: "show me X", "let me see X", "what does X look like". */
function asksToSee(words: readonly string[]): boolean {
  if (headWord(words) === "show") return true;
  return words.some((word, i) =>
    (word === "see" && asksToSeeAt(words, i)) ||
    ((word === "look" || word === "looks") && words[i + 1] === "like" && opensQuestion(words)));
}

/**
 * "Create a cat" heads a short message. "Make it shorter" changes something already there:
 * the server draws it only after a picture (`threadInvitesImage` asks then).
 */
function asksToMake(words: readonly string[]): boolean {
  const head = words.findIndex((word) => !LEAD_WORDS.has(word));
  return head >= 0 && MAKE_VERBS.has(words[head]) && !REVISION_PRONOUNS.has(words[head + 1] ?? "");
}

/**
 * Whether these words might ask for a picture or a photo. Whole words in the shape a
 * request takes, so a word that only names a picture in passing ("make" in "How do I make
 * a starter?", "image" in a lens question) sends the message straight to chat.
 */
function hasImageWord(text: string, imageAttached: boolean): boolean {
  const folded = text.toLowerCase();
  if (OTHER_LANGUAGE_WORDS.test(folded) || (imageAttached && EDIT_WORDS.test(folded))) return true;
  const short = text.trim().length <= SHORT_REQUEST;
  return sentences(folded).some((words) =>
    words.some((word) => DRAW_WORDS.has(word)) ||
    asksForPicture(words) ||
    asksToSee(words) ||
    (short && asksToMake(words)));
}

/** Whitespace to the phone or to the server (Python also splits on \x1c–\x1f and \x85). */
function isSpace(char: string): boolean {
  return /\s/.test(char) || ("\x1c" <= char && char <= "\x1f") || char === "\x85";
}

/** At most `SHORT_LINE` characters, not counting spaces or closing punctuation. */
function isShortLine(text: string): boolean {
  const kept = Array.from(text).filter((char) => !isSpace(char)).join("");
  return Array.from(kept.replace(CLOSING_PUNCTUATION, "")).length <= SHORT_LINE;
}

/** Rows the server has stored; a streaming, pending or optimistic row is the phone's alone. */
function storedRows(messages: readonly Row[]): Row[] {
  return messages.filter((row) =>
    row.id !== "streaming" &&
    row.id !== IMAGE_GEN_PENDING_ASSISTANT_ID &&
    row.id !== IMAGE_GEN_FAILED_ASSISTANT_ID &&
    !row.id.startsWith("local-"));
}

/**
 * After a picture any short line may edit it ("White"), and "do it" may confirm
 * a picture asked for just before: both need the chat, not the words.
 */
function threadInvitesImage(text: string, messages: readonly Row[]): boolean {
  const rows = storedRows(messages);
  const lastReply = [...rows].reverse().find((row) => row.role === "assistant");
  if (lastReply?.content.includes("[Image:")) return true;
  if (!isShortLine(text)) return false;
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const row = rows[i];
    if (row.role !== "user") continue;
    if (hasImageWord(row.content, false)) return true;
    if (!isShortLine(row.content)) return false;
  }
  return false;
}

/** True when the server should read this send before it goes to chat. */
export function mightBeImageTurn(
  text: string,
  messages: readonly Row[],
  imageAttached: boolean,
): boolean {
  return hasImageWord(text, imageAttached) || threadInvitesImage(text, messages);
}
