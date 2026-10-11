/**
 * Detect when the user wants image generation from plain composer text.
 * Matched intents generate immediately on send — no confirmation sheet.
 *
 * The server runs the same rules in apps/api/app/modules/images/gen_intent.py,
 * so a phrase the phone sends as chat is never generated on the server (and the
 * reverse). Each helper below has a same-named Python twin; change both, and the
 * shared cases in docs/fixtures/image_intent_cases.json, together.
 */

import { parseMessageImages } from "@/lib/messageAttachments";
import { isScannerCameraPrompt } from "@/lib/scanner/subjects";

export const IMAGE_GEN_PENDING_ASSISTANT_ID = "image-gen-pending";
export const IMAGE_GEN_FAILED_ASSISTANT_ID = "image-gen-failed";
export const IMAGE_GEN_USER_PREFIX = "Generate image: ";
const IMAGE_SEARCH_MODEL_ALIAS = "image-search-model";

const VERBS_IMAGE = new Set(["create", "generate", "make", "design", "render", "produce"]);
const VERBS_DRAW = new Set(["draw", "paint", "illustrate"]);
const IMAGE_NOUNS = new Set([
  "image",
  "images",
  "picture",
  "pictures",
  "pic",
  "pics",
  "photo",
  "photos",
  "illustration",
  "illustrations",
  "artwork",
  "artworks",
  "drawing",
  "drawings",
  "portrait",
  "portraits",
]);
const ARTICLES = new Set(["a", "an"]);
const POSSESSIVES = new Set(["my", "your", "our", "his", "her", "their", "its"]);
const REVISION_PRONOUNS = new Set(["it", "them", "this", "that"]);
const NOUN_MESSAGE_FILE_WORDS = new Set(["script", "code", "compression", "format", "file"]);
const SUBJECTLESS_FILLER = new Set(["a", "an", "the", "of", "just", "please"]);

/** Subjects that mean "make a thing in the app/code", not a picture. */
const NON_IMAGE_WORDS = new Set([
  "todo",
  "todos",
  "task",
  "tasks",
  "list",
  "lists",
  "reminder",
  "reminders",
  "project",
  "projects",
  "account",
  "accounts",
  "script",
  "scripts",
  "code",
  "function",
  "functions",
  "class",
  "classes",
  "file",
  "files",
  "folder",
  "folders",
  "chat",
  "chats",
  "note",
  "notes",
  "summary",
  "summaries",
  "plan",
  "plans",
  "schedule",
  "schedules",
  "event",
  "events",
  "meeting",
  "meetings",
  "quiz",
  "quizzes",
  "flashcard",
  "flashcards",
  "email",
  "emails",
  "message",
  "messages",
  "reply",
  "replies",
  "draft",
  "drafts",
  "report",
  "reports",
  "endpoint",
  "endpoints",
  "api",
  "apis",
  "database",
  "databases",
  "table",
  "tables",
  "component",
  "components",
  "hook",
  "hooks",
  "page",
  "pages",
  "screen",
  "screens",
  "modal",
  "modals",
  "button",
  "buttons",
  "form",
  "forms",
  "user",
  "users",
  "password",
  "passwords",
  "login",
  "logins",
  "pr",
  "prs",
  "commit",
  "commits",
  "branch",
  "branches",
  "issue",
  "issues",
  "bug",
  "bugs",
  "test",
  "tests",
  "array",
  "arrays",
  "object",
  "objects",
  "string",
  "strings",
  "comparison",
  "comparisons",
  // Learning / chat asks — "make your own example" is not a picture.
  "example",
  "examples",
  "problem",
  "problems",
  "equation",
  "equations",
  "question",
  "questions",
  "exercise",
  "exercises",
  "homework",
  "solution",
  "solutions",
  "proof",
  "proofs",
  "worksheet",
  "worksheets",
  "assignment",
  "assignments",
  // How-to / listicle heads — same as imageLookupIntent. Do not add
  // "way" (milky way) or "guide" (tour-guide photos).
  "stops",
  "ways",
  "tips",
  "tip",
  "secret",
  "secrets",
  "habit",
  "habits",
  "trick",
  "tricks",
  "stage",
  "stages",
  "phase",
  "phases",
  // "create music" is a chat ask, not a picture of an instrument.
  "music",
  "song",
  "songs",
  "playlist",
  "playlists",
  // Things the user wants built or written, not drawn.
  "app",
  "apps",
  "website",
  "websites",
  "game",
  "games",
  "program",
  "programs",
  "spreadsheet",
  "spreadsheets",
  "recipe",
  "recipes",
  "poem",
  "poems",
  "essay",
  "essays",
  "story",
  "stories",
  "joke",
  "jokes",
]);

const NON_IMAGE_DRAW_WORDS = new Set([
  "conclusion",
  "inference",
  "boundary",
  "line",
  "diagram",
  "chart",
  "graph",
  "plot",
  "flowchart",
  "flowcharts",
  // Verified ```geometry / ```smiles — not AI images.
  "triangle",
  "triangles",
  "square",
  "squares",
  "circle",
  "circles",
  "rectangle",
  "rectangles",
  "trapezoid",
  "trapezoids",
  "trapezium",
  "polygon",
  "polygons",
  "rhombus",
  "parallelogram",
  "geometry",
  "geometric",
  "hypotenuse",
  "molecule",
  "molecules",
  "molecular",
  "structure",
  "structures",
  "smiles",
  "chemistry",
  "chemical",
]);

const CODEISH_WORDS = new Set(["compression", "script", "code", "algorithm", "function", "api"]);

const EDGE_PUNCT = /^[.,!?;:"'()[\]]+|[.,!?;:"'()[\]]+$/g;

function tokens(text: string): string[] {
  return text.split(/\s+/).filter(Boolean);
}

function lower(token: string | undefined): string {
  return (token ?? "").toLowerCase();
}

/** Lowercase and strip edge punctuation so `tips,` matches `tips`. */
function foldToken(word: string): string {
  return word.toLowerCase().replace(EDGE_PUNCT, "");
}

function stripTrailing(text: string, chars: RegExp): string {
  return text.replace(chars, "");
}

function stripPolite(toks: string[]): string[] {
  let i = 0;
  if (lower(toks[i]) === "please") i += 1;
  if (i + 1 < toks.length && lower(toks[i]) === "can" && lower(toks[i + 1]) === "you") i += 2;
  return toks.slice(i);
}

function joinSubject(parts: string[]): string {
  return parts.join(" ").trim();
}

function cleanPrompt(raw: string): string | null {
  const prompt = stripTrailing(raw.trim(), /[.!?]+$/).trim();
  if (!prompt || prompt.length < 2) return null;
  if (tokens(prompt).some((word) => CODEISH_WORDS.has(foldToken(word)))) return null;
  return prompt;
}

function hasNonImageSubject(subject: string): boolean {
  const words = tokens(subject);
  for (let i = 0; i < words.length; i += 1) {
    const key = foldToken(words[i]);
    if (NON_IMAGE_WORDS.has(key)) return true;
    const next = i + 1 < words.length ? foldToken(words[i + 1]) : "";
    if (key === "pull" && (next === "request" || next === "requests")) return true;
  }
  return false;
}

function hasNonImageDraw(subject: string): boolean {
  const words = tokens(subject).map(foldToken);
  if (words.join(" ").includes("sketch of the idea")) return true;
  return words.some((word) => NON_IMAGE_DRAW_WORDS.has(word));
}

function isNonImageSubject(subject: string): boolean {
  return hasNonImageSubject(subject) || hasNonImageDraw(subject);
}

/** "the image" / "just a pic of" — only fillers and image nouns, no subject. */
function namesNoSubject(parts: string[]): boolean {
  return parts.every((tok) => IMAGE_NOUNS.has(foldToken(tok)) || SUBJECTLESS_FILLER.has(foldToken(tok)));
}

const MAX_IMAGE_MODIFIERS = 3;

/**
 * create/generate … image/pic … of? SUBJECT. A few words may describe the
 * picture first ("create a realistic photo of a dog"); they stay in the prompt,
 * so the subject must follow "of".
 */
function matchVerbThenImage(toks: string[]): string | null {
  if (toks.length < 3 || !VERBS_IMAGE.has(lower(toks[0]))) return null;
  let i = 1;
  if (lower(toks[i]) === "me") i += 1;
  if (ARTICLES.has(lower(toks[i]))) i += 1;
  const start = i;
  while (i < toks.length && i - start < MAX_IMAGE_MODIFIERS && !IMAGE_NOUNS.has(lower(toks[i]))) {
    i += 1;
  }
  if (i >= toks.length || !IMAGE_NOUNS.has(lower(toks[i]))) return null;
  if (i > start) {
    let rest = toks.slice(i + 2);
    if (rest.length && ARTICLES.has(lower(rest[0]))) rest = rest.slice(1);
    if (!rest.length || lower(toks[i + 1]) !== "of") return null;
    i = start;
  } else {
    i += 1;
    if (lower(toks[i]) === "of") i += 1;
  }
  if (i >= toks.length) return null;
  const subject = joinSubject(toks.slice(i));
  if (isNonImageSubject(subject)) return null;
  return cleanPrompt(subject);
}

/** create/generate … SUBJECT image/pic/photo */
function matchVerbSubjectImage(toks: string[]): string | null {
  if (toks.length < 3 || !VERBS_IMAGE.has(lower(toks[0]))) return null;
  if (!IMAGE_NOUNS.has(lower(toks[toks.length - 1]))) return null;
  let i = 1;
  if (i < toks.length - 1 && lower(toks[i]) === "me") i += 1;
  if (i < toks.length - 1 && ARTICLES.has(lower(toks[i]))) i += 1;
  const parts = toks.slice(i, -1);
  if (!parts.length || namesNoSubject(parts)) return null;
  const subject = joinSubject(parts);
  if (isNonImageSubject(subject)) return null;
  return cleanPrompt(subject);
}

/** draw/paint/illustrate me [a/an] SUBJECT */
function matchDrawMe(toks: string[]): string | null {
  if (toks.length < 3 || !VERBS_DRAW.has(lower(toks[0])) || lower(toks[1]) !== "me") return null;
  let i = 2;
  if (ARTICLES.has(lower(toks[i]))) i += 1;
  if (i >= toks.length) return null;
  const subject = joinSubject(toks.slice(i));
  if (isNonImageSubject(subject)) return null;
  return cleanPrompt(subject);
}

/** "make money" / "make dinner". A picture that uses "make" names an image noun. */
const MAKE_NOT_A_PICTURE = new Set([
  "money",
  "cash",
  "bank",
  "profit",
  "profits",
  "income",
  "living",
  "sense",
  "time",
  "friends",
  "friend",
  "decision",
  "decisions",
  "point",
  "progress",
  "mistake",
  "mistakes",
  "amends",
  "peace",
  "difference",
  "room",
  "haste",
  "dinner",
  "lunch",
  "breakfast",
  "bed",
  "love",
  "ends",
  "laugh",
  "smile",
]);
const MAKE_IDIOM_FILLER = new Set(["a", "an", "the", "some", "more", "much", "of", "lot", "lots"]);

function makeIsNotAPicture(subject: string): boolean {
  const words = tokens(subject)
    .map(foldToken)
    .filter((word) => word.length > 0 && !MAKE_IDIOM_FILLER.has(word));
  return words.length > 0 && words.every((word) => MAKE_NOT_A_PICTURE.has(word));
}

/**
 * Short "draw a dog" or "create a cat" — the whole message is the subject.
 * "make your own example" still fails the non-image list; "make money" is not
 * a picture; "make a cat photo" is matched earlier.
 */
function matchShortCreate(toks: string[]): string | null {
  if (toks.length < 2) return null;
  const verb = lower(toks[0]);
  if (!VERBS_DRAW.has(verb) && !VERBS_IMAGE.has(verb)) return null;
  let i = 1;
  if (lower(toks[i]) === "me") i += 1;
  if (ARTICLES.has(lower(toks[i]))) i += 1;
  const parts = toks.slice(i);
  if (!parts.length || parts.length > 8) return null;
  if (REVISION_PRONOUNS.has(lower(parts[0]))) return null;
  // "create an image" names no subject; the thread may supply one.
  if (namesNoSubject(parts)) return null;
  const subject = joinSubject(parts);
  if (verb === "make" && makeIsNotAPicture(subject)) return null;
  if (isNonImageSubject(subject)) return null;
  return cleanPrompt(subject);
}

/**
 * Short colloquial ask: "cat pic" / "a sunset photo" / "photo of a cat". The
 * image noun must close the message, or open it before "of". A noun in the
 * middle ("best photo editing apps", "picture this") is ordinary chat, and so
 * is a question or a possessive ("how to take a good photo").
 */
function matchImageNounMessage(toks: string[]): string | null {
  if (toks.length < 2 || toks.length > 16) return null;
  const folded = toks.map(foldToken);
  let parts: string[];
  if (IMAGE_NOUNS.has(folded[folded.length - 1])) {
    parts = toks.slice(0, -1);
  } else {
    const i = ARTICLES.has(folded[0]) ? 1 : 0;
    if (i + 1 >= toks.length || !IMAGE_NOUNS.has(folded[i]) || folded[i + 1] !== "of") return null;
    parts = toks.slice(i + 2);
  }
  if (parts.length && ARTICLES.has(foldToken(parts[0]))) parts = parts.slice(1);
  if (!parts.length || namesNoSubject(parts)) return null;
  const first = foldToken(parts[0]);
  if (
    POSSESSIVES.has(first) ||
    NOT_REVISION_STARTERS.has(first) ||
    IMAGE_NOUNS.has(first) ||
    VERBS_IMAGE.has(first) ||
    VERBS_DRAW.has(first)
  ) {
    return null;
  }
  if (parts.some((word) => NOUN_MESSAGE_FILE_WORDS.has(foldToken(word)))) return null;
  const subject = joinSubject(parts);
  if (isNonImageSubject(subject)) return null;
  return cleanPrompt(subject);
}

function startsWithUserPrefix(text: string): boolean {
  return text.toLowerCase().startsWith(IMAGE_GEN_USER_PREFIX.toLowerCase());
}

/** Return the image subject if `text` is a clear image-gen ask, else null. */
export function extractImageGenPrompt(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > 500) return null;
  // Scanner captions contain "image" and are often ≤80 chars, which the
  // short image-noun heuristic would steal as a generate-image ask.
  if (isScannerCameraPrompt(trimmed)) return null;
  if (startsWithUserPrefix(trimmed)) return cleanPrompt(trimmed.slice(IMAGE_GEN_USER_PREFIX.length));

  const toks = stripPolite(tokens(trimmed));
  if (!toks.length) return null;

  const matched = matchVerbThenImage(toks) ?? matchVerbSubjectImage(toks) ?? matchDrawMe(toks);
  if (matched) return matched;
  // Short create/draw only when the whole message is short.
  if (trimmed.length <= 80) return matchShortCreate(toks) ?? matchImageNounMessage(toks);
  return null;
}

const NOUN_ONLY_FILLER = new Set(["please", "a", "an", "the", "just"]);

const GENERATE_NOW_EXACT = new Set([
  "that works",
  "that will work",
  "that works for me",
  "do it",
  "do that",
  "go ahead",
  "go for it",
  "generate it",
  "generate that",
  "generate the image",
  "generate the picture",
  "you do it",
  "u do it",
  "you pick",
  "u pick",
  "you choose",
  "u choose",
]);

/** True for a bare image ask with no subject: "Image", "a pic", "create an image". */
export function isImageNounOnlyMessage(text: string): boolean {
  if (isImageGenGenerateNow(text)) return false;
  let toks = stripPolite(tokens(stripTrailing(text.trim(), /[.!?]+$/)));
  if (toks.length && (VERBS_IMAGE.has(lower(toks[0])) || VERBS_DRAW.has(lower(toks[0])))) {
    toks = toks.slice(1);
    if (lower(toks[0]) === "me") toks = toks.slice(1);
  }
  const kept = toks.filter((tok) => !NOUN_ONLY_FILLER.has(lower(tok)));
  if (!kept.length) return false;
  return kept.every((tok) => IMAGE_NOUNS.has(lower(tok)));
}

/** True when this line is "do it" / "that works" / "u pick" after a scene. */
export function isImageGenGenerateNow(text: string): boolean {
  const collapsed = stripTrailing(tokens(text.trim().toLowerCase()).join(" "), /[.!?]+$/).trim();
  if (!collapsed || collapsed.length > 40) return false;
  if (GENERATE_NOW_EXACT.has(collapsed)) return true;
  const padded = ` ${collapsed} `;
  return padded.includes(" do it ") || padded.includes(" u do it ") || padded.includes(" you do it ");
}

/** Prior user line usable as a generate subject (short concrete noun). */
function threadSubjectFromUser(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > 80 || trimmed.includes("?")) return null;
  if (isImageNounOnlyMessage(trimmed) || isImageGenGenerateNow(trimmed)) return null;
  const existing = extractImageGenPrompt(trimmed);
  if (existing) return existing;
  const words = tokens(trimmed);
  if (!words.length || words.length > 6) return null;
  const first = stripTrailing(lower(words[0]), /[.!,]+$/);
  if (NOT_REVISION_STARTERS.has(first)) return null;
  if (isNonImageSubject(trimmed)) return null;
  const cleaned = cleanPrompt(trimmed);
  if (!cleaned || NON_REVISION.has(cleaned.toLowerCase())) return null;
  return cleaned;
}

const DEICTIC_SUBJECTS = new Set(["that", "this", "it", "them"]);

function isDeicticSubject(subject: string): boolean {
  const first = tokens(subject)[0];
  return first !== undefined && DEICTIC_SUBJECTS.has(foldToken(first));
}

function resolveDeicticSubject(direct: string, priors: readonly string[]): string {
  if (!isDeicticSubject(direct)) return direct;
  for (let i = priors.length - 1; i >= 0; i -= 1) {
    const subject = extractImageGenPrompt(priors[i] ?? "");
    if (subject && !isDeicticSubject(subject)) return subject;
  }
  return direct;
}

/** Confirm ("do it") only against the current image exchange, not any older ask. */
function subjectFromActiveImageExchange(priors: readonly string[]): string | null {
  let skippedNounOnly = false;
  for (let i = priors.length - 1; i >= 0; i -= 1) {
    const prior = priors[i] ?? "";
    if (isImageGenGenerateNow(prior)) continue;
    if (isImageNounOnlyMessage(prior)) {
      skippedNounOnly = true;
      continue;
    }
    const explicit = extractImageGenPrompt(prior);
    if (explicit) return explicit;
    if (skippedNounOnly) return threadSubjectFromUser(prior);
    return null;
  }
  return null;
}

function skipImageGenHistoryRow(row: { id: string }): boolean {
  return (
    row.id === "streaming" ||
    row.id === IMAGE_GEN_PENDING_ASSISTANT_ID ||
    row.id === IMAGE_GEN_FAILED_ASSISTANT_ID ||
    row.id.startsWith("local-")
  );
}

/**
 * Current line plus prior user bubbles: "Dog" then "Image" / "that works".
 * A picture of "that car" uses the previous concrete subject.
 * Mirrors API `extract_image_gen_prompt_from_thread`.
 */
export function extractImageGenPromptFromThread(
  text: string,
  messages: readonly { id: string; role: string; content: string; model?: string | null }[],
): string | null {
  const priors: string[] = [];
  for (const row of messages) {
    if (skipImageGenHistoryRow(row)) continue;
    if (row.role === "user") priors.push(row.content);
  }
  if (priors.length && priors[priors.length - 1]?.trim() === text.trim()) {
    priors.pop();
  }
  const direct = extractImageGenPrompt(text);
  if (direct) return resolveDeicticSubject(direct, priors);
  if (isImageNounOnlyMessage(text)) {
    for (let i = priors.length - 1; i >= 0; i -= 1) {
      const subject = threadSubjectFromUser(priors[i] ?? "");
      if (subject) return subject;
    }
    return null;
  }
  if (!isImageGenGenerateNow(text)) return null;
  return subjectFromActiveImageExchange(priors);
}

const REACTION_WORDS = new Set([
  "nice",
  "cool",
  "great",
  "love",
  "wow",
  "beautiful",
  "awesome",
  "perfect",
  "cute",
]);

const REACTION_PHRASES = new Set([
  "looks good",
  "looks great",
  "looks nice",
  "love it",
  "love this",
  "so cool",
  "so nice",
  "well done",
  "nice one",
]);

function isReaction(text: string): boolean {
  let collapsed = stripTrailing(tokens(text.trim().toLowerCase()).join(" "), /[.!?]+$/).trim();
  if (collapsed.startsWith("please ")) collapsed = collapsed.slice("please ".length).trim();
  if (!collapsed) return false;
  if (REACTION_PHRASES.has(collapsed)) return true;
  return REACTION_WORDS.has(collapsed.split(" ")[0] ?? "");
}

function hasEditLeadIn(toks: string[]): boolean {
  let i = 0;
  if (lower(toks[i]) === "please") i += 1;
  const word = lower(toks[i]);
  const next = lower(toks[i + 1]);
  if (i + 1 < toks.length && (word === "make" || word === "change") && (next === "it" || next === "them")) {
    return true;
  }
  return i < toks.length && ["now", "again", "instead", "try"].includes(word);
}

const NON_REVISION = new Set([
  "ok",
  "okay",
  "k",
  "thanks",
  "thank you",
  "thx",
  "ty",
  "yes",
  "no",
  "yep",
  "nope",
  "sure",
  "cool",
  "nice",
  "lol",
  "lmao",
  "haha",
  "hehe",
  "great",
  "got it",
  "perfect",
  "awesome",
  "hi",
  "hello",
  "hey",
  "hiya",
  "yo",
  "sup",
  "bye",
  "goodbye",
  "cya",
  "see ya",
  "sounds good",
  "makes sense",
  "understood",
]);

/**
 * First remaining token after revision lead-ins. Questions and chat openers
 * must not become "{subject}, what's 2+2".
 */
const NOT_REVISION_STARTERS = new Set([
  "what",
  "what's",
  "whats",
  "why",
  "how",
  "how's",
  "who",
  "when",
  "where",
  "which",
  "can",
  "could",
  "would",
  "should",
  "is",
  "are",
  "do",
  "does",
  "did",
  "will",
  "am",
  "help",
  "show",
  "tell",
  "explain",
  "write",
  "please",
  "i",
  "i'm",
  "im",
  "i've",
  "ive",
  "we",
  "let's",
  "lets",
]);

/**
 * "show it at night" / "show the car in blue" redraw the last picture; "show the
 * steps" or "show 23 × 14" after a picture are ordinary chat.
 */
const SHOW_REVISION_TARGETS = new Set(["it", "them", "more", "less", "another", "a", "an", "the"]);
const SHOW_NON_IMAGE_WORDS = new Set([
  "step",
  "steps",
  "work",
  "working",
  "workout",
  "answer",
  "solution",
  "calculation",
  "how",
]);
const SHOW_NON_IMAGE_SYMBOLS = ["+", "-", "×", "÷", "*", "/", "=", "^"];

function isShowImageRevision(toks: string[]): boolean {
  if (toks.length < 3 || lower(toks[0]) !== "show") return false;
  if (toks.some((tok) => SHOW_NON_IMAGE_SYMBOLS.some((symbol) => tok.includes(symbol)))) return false;
  const words = toks.map(foldToken);
  if (words.some((word) => SHOW_NON_IMAGE_WORDS.has(word))) return false;
  if (words.some((word, i) => word === "long" && words[i + 1] === "division")) return false;
  return SHOW_REVISION_TARGETS.has(words[1]);
}

/** Subject from a prior image-gen user bubble (legacy prefix or natural wording). */
export function subjectFromImageGenUserMessage(content: string): string | null {
  const trimmed = content.trim();
  if (startsWithUserPrefix(trimmed)) return cleanPrompt(trimmed.slice(IMAGE_GEN_USER_PREFIX.length));
  return extractImageGenPrompt(trimmed);
}

/** True when the assistant bubble is only an `[Image: …]` marker (no prose). */
export function isImageOnlyAssistantContent(content: string): boolean {
  const { images, textWithoutImages } = parseMessageImages(content);
  return images.length > 0 && textWithoutImages.trim().length === 0;
}

function isImageGenAssistantRow(row: { content: string; model?: string | null }): boolean {
  if (row.model === IMAGE_SEARCH_MODEL_ALIAS) return false;
  return isImageOnlyAssistantContent(row.content);
}

/** Drop "make it" / "change them to" / "now" style lead-ins. */
function stripRevisionLeadIn(toks: string[]): string[] {
  let i = 0;
  if (lower(toks[i]) === "please") i += 1;
  const word = lower(toks[i]);
  const next = lower(toks[i + 1]);
  if (i + 1 < toks.length && word === "make" && (next === "it" || next === "them")) {
    return toks.slice(i + 2);
  }
  if (i + 1 < toks.length && word === "change" && (next === "it" || next === "them")) {
    let j = i + 2;
    if (lower(toks[j]) === "to") j += 1;
    return toks.slice(j);
  }
  if (i < toks.length && ["now", "again", "instead", "try"].includes(word)) return toks.slice(i + 1);
  return toks.slice(i);
}

/**
 * Short follow-up after an image-only reply ("White", "make it blue") → new
 * generate prompt. Returns null when this is normal chat.
 */
export function extractImageRevisionPrompt(
  text: string,
  opts: {
    lastAssistantIsImageOnly: boolean;
    previousSubject: string | null;
  },
): string | null {
  if (!opts.lastAssistantIsImageOnly || !opts.previousSubject) return null;
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > 120) return null;
  if (!hasEditLeadIn(tokens(trimmed)) && isReaction(trimmed)) return null;

  const toks = stripRevisionLeadIn(tokens(trimmed));
  if (!toks.length || toks.length > 8) return null;
  if (trimmed.includes("?")) return null;
  const first = stripTrailing(lower(toks[0]), /[.!,]+$/);
  if (NOT_REVISION_STARTERS.has(first) && !isShowImageRevision(toks)) return null;
  const revision = joinSubject(toks);
  if (!revision || hasNonImageSubject(revision)) return null;
  const cleaned = cleanPrompt(revision);
  if (!cleaned || NON_REVISION.has(cleaned.toLowerCase())) return null;
  return `${opts.previousSubject}, ${cleaned}`;
}

/** Walk newest→oldest for image-gen context used by revision intercept. */
export function imageGenRevisionContext(
  messages: readonly { id: string; role: string; content: string; model?: string | null }[],
): { lastAssistantIsImageOnly: boolean; previousSubject: string | null; referenceAttachmentId?: string } {
  let lastAssistantIsImageOnly = false;
  let previousSubject: string | null = null;
  let referenceAttachmentId: string | undefined;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const row = messages[i];
    if (skipImageGenHistoryRow(row)) continue;
    if (!lastAssistantIsImageOnly && row.role === "assistant") {
      lastAssistantIsImageOnly = isImageGenAssistantRow(row);
      referenceAttachmentId = parseMessageImages(row.content).images[0]?.attachmentId ?? undefined;
      if (!lastAssistantIsImageOnly) {
        // Latest assistant isn't an image-gen reply — don't treat follow-ups as revisions.
        break;
      }
      continue;
    }
    if (lastAssistantIsImageOnly && row.role === "user") {
      previousSubject = subjectFromImageGenUserMessage(row.content) ?? "the provided image";
      break;
    }
  }
  return { lastAssistantIsImageOnly, previousSubject,
    ...(referenceAttachmentId ? { referenceAttachmentId } : {}) };
}

/** Only explicit transformations of an attached image, not questions about it. */
export function extractAttachedImageEditPrompt(text: string): string | null {
  const cleaned = text.trim();
  return /^(?:please\s+)?(?:(?:can|could) you\s+)?(?:edit|change|remove|replace|recolor|crop|transform|turn|make)\b/i.test(cleaned)
    && cleaned.length <= 2000 ? cleaned : null;
}
