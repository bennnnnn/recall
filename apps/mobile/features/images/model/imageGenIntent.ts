/**
 * Detect when the user wants image generation from plain composer text.
 * Matched intents generate immediately on send — no confirmation sheet.
 */

import { parseMessageImages } from "@/lib/messageAttachments";
import { isScannerCameraPrompt } from "@/lib/scanner/subjects";

export const IMAGE_GEN_PENDING_ASSISTANT_ID = "image-gen-pending";
export const IMAGE_GEN_FAILED_ASSISTANT_ID = "image-gen-failed";
export const IMAGE_GEN_USER_PREFIX = "Generate image: ";
const IMAGE_SEARCH_MODEL_ALIAS = "image-search-model";

/** Subject from a prior image-gen user bubble (legacy prefix or natural wording). */
export function subjectFromImageGenUserMessage(content: string): string | null {
  const trimmed = content.trim();
  if (trimmed.toLowerCase().startsWith(IMAGE_GEN_USER_PREFIX.toLowerCase())) {
    return cleanPrompt(trimmed.slice(IMAGE_GEN_USER_PREFIX.length));
  }
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

const REVISION_LEAD_IN =
  /^(?:please\s+)?(?:make it|make them|change (?:it|them)(?:\s+to)?|now|again|instead|try)\s+/i;

const NON_REVISION =
  /^(?:ok|okay|thanks|thank you|yes|no|sure|cool|nice|lol|great|got it|perfect)$/i;

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
  const collapsed = text
    .trim()
    .replace(/^(?:please\s+)/i, "")
    .replace(/[.!?]+$/g, "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
  if (!collapsed) return false;
  if (REACTION_PHRASES.has(collapsed)) return true;
  const first = collapsed.split(" ")[0] ?? "";
  return REACTION_WORDS.has(first);
}

const SHOW_IMAGE_REVISION =
  /^show\s+(?:it|them|more|less|another\b|an?\s+|the\s+(?!steps?\b|work(?:ing|out)?\b|answer\b|solution\b|calculation\b|long\s+division\b)).+/i;

const SHOW_NON_IMAGE_REQUEST =
  /(?:[+\-×÷*/=^]|\b(?:long\s+division|steps?|work(?:ing|out)?|answer|solution|calculation|how)\b)/i;

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

  let revision = trimmed;
  const lead = trimmed.match(REVISION_LEAD_IN);
  if (lead) {
    revision = trimmed.slice(lead[0].length).trim();
  }
  if (!lead && isReaction(trimmed)) return null;
  if (!revision || revision.split(/\s+/).length > 8) return null;
  if (trimmed.includes("?")) return null;
  const first = revision.split(/\s+/)[0]?.toLowerCase().replace(/[.!,]+$/, "") ?? "";
  const showImageRevision =
    first === "show" &&
    SHOW_IMAGE_REVISION.test(revision) &&
    !SHOW_NON_IMAGE_REQUEST.test(revision);
  if (NOT_REVISION_STARTERS.has(first) && !showImageRevision) return null;
  if (NON_IMAGE_SUBJECT.test(revision) || NON_REVISION.test(revision)) return null;
  const cleaned = cleanPrompt(revision);
  if (!cleaned) return null;
  return `${opts.previousSubject}, ${cleaned}`;
}

/** Walk newest→oldest for image-gen context used by revision intercept. */
export function imageGenRevisionContext(
  messages: ReadonlyArray<{ id: string; role: string; content: string; model?: string | null }>,
): { lastAssistantIsImageOnly: boolean; previousSubject: string | null; referenceAttachmentId?: string } {
  let lastAssistantIsImageOnly = false;
  let previousSubject: string | null = null;
  let referenceAttachmentId: string | undefined;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const row = messages[i];
    if (
      row.id === "streaming" ||
      row.id === IMAGE_GEN_PENDING_ASSISTANT_ID ||
      row.id === IMAGE_GEN_FAILED_ASSISTANT_ID ||
      row.id.startsWith("local-")
    ) {
      continue;
    }
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

const IMAGE_NOUN =
  /\b(?:images?|pictures?|pics?|photos?|illustrations?|artworks?|drawings?|portraits?)\b/i;

/** "create/generate … image/pic … of X" or "create a cat pic" */
const VERB_THEN_IMAGE = new RegExp(
  String.raw`^(?:please\s+)?(?:can you\s+)?` +
    String.raw`(?:create|generate|make|design|render|produce)\s+` +
    String.raw`(?:me\s+)?(?:an?\s+)?` +
    String.raw`(?:image|picture|pic|photo|illustration|artwork|drawing|portrait)\s+` +
    String.raw`(?:of\s+)?(.+)$`,
  "i",
);

/** "create/generate a cat pic" — subject before image noun */
const VERB_SUBJECT_IMAGE = new RegExp(
  String.raw`^(?:please\s+)?(?:can you\s+)?` +
    String.raw`(?:create|generate|make|design|render|produce)\s+` +
    String.raw`(?:me\s+)?(?:an?\s+)?(.+?)\s+` +
    String.raw`(?:image|picture|pic|photo|illustration|artwork|drawing|portrait)$`,
  "i",
);

/** "draw/paint me a cat" — no literal "image" word */
const DRAW_ME = new RegExp(
  String.raw`^(?:please\s+)?(?:can you\s+)?(?:draw|paint|illustrate)\s+me\s+(?:an?\s+)?(.+)$`,
  "i",
);

/**
 * Short "draw a dog" or "create a cat" without an image noun. Anchored
 * full-message only. "make your own example" still fails the non-image list.
 */
const SHORT_DRAW_SUBJECT = new RegExp(
  String.raw`^(?:please\s+)?(?:can you\s+)?` +
    String.raw`(?:draw|paint|illustrate)\s+` +
    String.raw`(?:me\s+)?(?:an?\s+)?(.+)$`,
  "i",
);

const SHORT_CREATE_SUBJECT = new RegExp(
  String.raw`^(?:please\s+)?(?:can you\s+)?` +
    String.raw`(?:create|generate|make|design|render|produce)\s+` +
    String.raw`(?:me\s+)?(?:an?\s+)?(.+)$`,
  "i",
);

const NON_IMAGE_DRAW = new RegExp(
  String.raw`\b(?:conclusion|inference|boundary|line|diagram|chart|graph|plot|flowcharts?|sketch\s+of\s+the\s+idea|triangles?|squares?|circles?|rectangles?|trapezoids?|trapezium|polygons?|rhombus|parallelogram|geometry|geometric|hypotenuse|molecules?|molecular|structures?|smiles|chemistry|chemical)\b`,
  "i",
);

/** Subjects that mean "make a thing in the app/code", not a picture. */
const NON_IMAGE_SUBJECT = new RegExp(
  String.raw`\b(?:` +
    [
      "todos?",
      "tasks?",
      "lists?",
      "reminders?",
      "projects?",
      "accounts?",
      "scripts?",
      "code",
      "functions?",
      "classes?",
      "files?",
      "folders?",
      "chats?",
      "notes?",
      "summar(?:y|ies)",
      "plans?",
      "schedules?",
      "events?",
      "meetings?",
      "quizzes?",
      "flashcards?",
      "emails?",
      "messages?",
      "replies?",
      "drafts?",
      "reports?",
      "endpoints?",
      "apis?",
      "databases?",
      "tables?",
      "components?",
      "hooks?",
      "pages?",
      "screens?",
      "modals?",
      "buttons?",
      "forms?",
      "users?",
      "passwords?",
      "logins?",
      "prs?",
      "pull\\s+requests?",
      "commits?",
      "branches?",
      "issues?",
      "bugs?",
      "tests?",
      "arrays?",
      "objects?",
      "strings?",
      "comparisons?",
      // Learning / chat asks — "make your own example" is not a picture.
      "examples?",
      "problems?",
      "equations?",
      "questions?",
      "exercises?",
      "homework",
      "solutions?",
      "proofs?",
      "worksheets?",
      "assignments?",
      // How-to / listicle heads — same as imageLookupIntent. Do not add
      // "way" (milky way) or "guide" (tour-guide photos).
      "stops",
      "ways",
      "tips?",
      "secrets?",
      "habits?",
      "tricks?",
      "stages?",
      "phases?",
      // "create music" is a chat ask, not a picture of an instrument.
      "music",
      "songs?",
      "playlists?",
    ].join("|") +
    String.raw`)\b`,
  "i",
);

function cleanPrompt(raw: string): string | null {
  const prompt = raw
    .trim()
    .replace(/[.!?]+$/g, "")
    .trim();
  if (!prompt || prompt.length < 2) return null;
  if (/\b(?:compression|script|code|algorithm|function|api)\b/i.test(prompt)) return null;
  return prompt;
}

function isNonImageSubject(subject: string): boolean {
  return NON_IMAGE_SUBJECT.test(subject) || NON_IMAGE_DRAW.test(subject);
}

function extractShortVerbSubject(trimmed: string, pattern: RegExp): string | null {
  if (trimmed.length > 80) return null;
  const match = trimmed.match(pattern);
  if (!match?.[1]) return null;
  const subject = match[1].trim();
  if (subject.split(/\s+/).length > 8) return null;
  if (/^(?:it|them|this|that)\b/i.test(subject)) return null;
  if (isNonImageSubject(subject)) return null;
  return cleanPrompt(subject);
}

function extractShortDrawSubject(trimmed: string): string | null {
  return extractShortVerbSubject(trimmed, SHORT_DRAW_SUBJECT);
}

function extractShortCreateSubject(trimmed: string): string | null {
  return extractShortVerbSubject(trimmed, SHORT_CREATE_SUBJECT);
}

export function extractImageGenPrompt(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > 500) return null;
  // Scanner captions contain "image" and are often ≤80 chars, which the
  // short image-noun heuristic would steal as a generate-image ask.
  if (isScannerCameraPrompt(trimmed)) return null;

  let match = trimmed.match(VERB_THEN_IMAGE);
  if (match?.[1]) {
    if (isNonImageSubject(match[1])) return null;
    return cleanPrompt(match[1]);
  }

  match = trimmed.match(VERB_SUBJECT_IMAGE);
  if (match?.[1]) {
    if (isNonImageSubject(match[1])) return null;
    return cleanPrompt(match[1]);
  }

  match = trimmed.match(DRAW_ME);
  if (match?.[1]) {
    const subject = match[1];
    if (isNonImageSubject(subject)) return null;
    return cleanPrompt(subject);
  }

  const shortDraw = extractShortDrawSubject(trimmed);
  if (shortDraw) return shortDraw;

  const shortCreate = extractShortCreateSubject(trimmed);
  if (shortCreate) return shortCreate;

  // Short colloquial: "cat pic" / "sunset photo" as full message
  if (trimmed.length <= 80 && IMAGE_NOUN.test(trimmed)) {
    const stripped = trimmed
      .replace(IMAGE_NOUN, "")
      .replace(/^(?:an?\s+)/i, "")
      .trim();
    if (
      stripped.length >= 2 &&
      !/\b(?:script|code|compression|format|file)\b/i.test(stripped) &&
      !isNonImageSubject(stripped)
    ) {
      return cleanPrompt(stripped);
    }
  }

  return null;
}

const IMAGE_NOUN_SET = new Set([
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

const NOUN_ONLY_FILLER = new Set(["please", "a", "an", "the", "just"]);

const NOT_THREAD_SUBJECT = new Set([
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

const DEICTIC_SUBJECT = /^(?:that|this|it|them)\b/i;

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

function skipImageGenHistoryRow(row: { id: string }): boolean {
  return (
    row.id === "streaming" ||
    row.id === IMAGE_GEN_PENDING_ASSISTANT_ID ||
    row.id === IMAGE_GEN_FAILED_ASSISTANT_ID ||
    row.id.startsWith("local-")
  );
}

function tokenWord(token: string): string {
  return token.toLowerCase().replace(/[.!?]+$/g, "");
}

export function isImageNounOnlyMessage(text: string): boolean {
  const trimmed = text.trim().replace(/[.!?]+$/g, "").trim();
  if (!trimmed) return false;
  const tokens = trimmed.split(/\s+/).filter(Boolean);
  const kept = tokens.filter((tok) => {
    const word = tokenWord(tok);
    return !NOUN_ONLY_FILLER.has(word);
  });
  if (kept.length === 0) return false;
  return kept.every((tok) => IMAGE_NOUN_SET.has(tokenWord(tok)));
}

export function isImageGenGenerateNow(text: string): boolean {
  const collapsed = text.trim().toLowerCase().replace(/\s+/g, " ").replace(/[.!?]+$/g, "").trim();
  if (!collapsed || collapsed.length > 40) return false;
  if (GENERATE_NOW_EXACT.has(collapsed)) return true;
  const padded = ` ${collapsed} `;
  return padded.includes(" do it ") || padded.includes(" u do it ") || padded.includes(" you do it ");
}

function threadSubjectFromUser(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > 80 || trimmed.includes("?")) return null;
  if (isImageNounOnlyMessage(trimmed) || isImageGenGenerateNow(trimmed)) return null;
  const existing = extractImageGenPrompt(trimmed);
  if (existing) return existing;
  const words = trimmed.split(/\s+/).filter(Boolean);
  if (!words.length || words.length > 6) return null;
  const first = tokenWord(words[0] ?? "");
  if (NOT_REVISION_STARTERS.has(first)) return null;
  if (isNonImageSubject(trimmed)) return null;
  const cleaned = cleanPrompt(trimmed);
  if (!cleaned || NON_REVISION.test(cleaned) || NOT_THREAD_SUBJECT.has(cleaned.toLowerCase())) {
    return null;
  }
  return cleaned;
}

function resolveDeicticSubject(direct: string, priors: readonly string[]): string {
  if (!DEICTIC_SUBJECT.test(direct)) return direct;
  for (let i = priors.length - 1; i >= 0; i -= 1) {
    const subject = extractImageGenPrompt(priors[i] ?? "");
    if (subject && !DEICTIC_SUBJECT.test(subject)) return subject;
  }
  return direct;
}

/**
 * Current line plus prior user bubbles: "Dog" then "Image" / "that works".
 * A picture of "that car" uses the previous concrete subject.
 * Mirrors API ``extract_image_gen_prompt_from_thread``.
 */
export function extractImageGenPromptFromThread(
  text: string,
  messages: ReadonlyArray<{ id: string; role: string; content: string; model?: string | null }>,
): string | null {
  const direct = extractImageGenPrompt(text);
  const priors: string[] = [];
  for (const row of messages) {
    if (skipImageGenHistoryRow(row)) continue;
    if (row.role === "user") priors.push(row.content);
  }
  if (priors.length && priors[priors.length - 1]?.trim() === text.trim()) {
    priors.pop();
  }
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
