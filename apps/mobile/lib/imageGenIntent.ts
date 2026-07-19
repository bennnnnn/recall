/**
 * Detect when the user wants image generation from plain composer text.
 * Matched intents generate immediately on send — no confirmation sheet.
 */

export const IMAGE_GEN_PENDING_ASSISTANT_ID = "image-gen-pending";

export function imageGenUserMessageContent(prompt: string): string {
  return `Generate image: ${prompt}`;
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
 * Short "create/draw a cat" without an image noun. Anchored full-message only;
 * non-visual subjects are rejected below.
 */
const CREATE_OR_DRAW_SUBJECT = new RegExp(
  String.raw`^(?:please\s+)?(?:can you\s+)?` +
    String.raw`(?:create|generate|make|draw|paint|illustrate)\s+` +
    String.raw`(?:me\s+)?(?:an?\s+)?(.+)$`,
  "i",
);

const NON_IMAGE_DRAW = new RegExp(
  String.raw`\b(?:conclusion|inference|boundary|line|diagram|chart|graph|plot|sketch\s+of\s+the\s+idea)\b`,
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

function extractShortCreateSubject(trimmed: string): string | null {
  if (trimmed.length > 80) return null;
  const match = trimmed.match(CREATE_OR_DRAW_SUBJECT);
  if (!match?.[1]) return null;
  const subject = match[1].trim();
  if (subject.split(/\s+/).length > 8) return null;
  if (NON_IMAGE_SUBJECT.test(subject) || NON_IMAGE_DRAW.test(subject)) return null;
  return cleanPrompt(subject);
}

export function extractImageGenPrompt(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > 500) return null;

  let match = trimmed.match(VERB_THEN_IMAGE);
  if (match?.[1]) {
    return cleanPrompt(match[1]);
  }

  match = trimmed.match(VERB_SUBJECT_IMAGE);
  if (match?.[1]) {
    return cleanPrompt(match[1]);
  }

  match = trimmed.match(DRAW_ME);
  if (match?.[1]) {
    const subject = match[1];
    if (NON_IMAGE_DRAW.test(subject)) return null;
    return cleanPrompt(subject);
  }

  const shortCreate = extractShortCreateSubject(trimmed);
  if (shortCreate) return shortCreate;

  // Short colloquial: "cat pic" / "sunset photo" as full message
  if (trimmed.length <= 80 && IMAGE_NOUN.test(trimmed)) {
    const stripped = trimmed
      .replace(IMAGE_NOUN, "")
      .replace(/^(?:an?\s+)/i, "")
      .trim();
    if (stripped.length >= 2 && !/\b(?:script|code|compression|format|file)\b/i.test(stripped)) {
      return cleanPrompt(stripped);
    }
  }

  return null;
}
