/**
 * Detect when the user wants image generation from plain composer text.
 * Matched intents generate immediately on send — no confirmation sheet.
 */

import { parseMessageImages } from "@/lib/messageAttachments";

export const IMAGE_GEN_PENDING_ASSISTANT_ID = "image-gen-pending";
export const IMAGE_GEN_USER_PREFIX = "Generate image: ";

export function imageGenUserMessageContent(prompt: string): string {
  return `${IMAGE_GEN_USER_PREFIX}${prompt}`;
}

/** Subject from a prior "Generate image: …" user bubble, if any. */
export function subjectFromImageGenUserMessage(content: string): string | null {
  const trimmed = content.trim();
  if (!trimmed.toLowerCase().startsWith(IMAGE_GEN_USER_PREFIX.toLowerCase())) {
    return null;
  }
  return cleanPrompt(trimmed.slice(IMAGE_GEN_USER_PREFIX.length));
}

/** True when the assistant bubble is only an `[Image: …]` marker (no prose). */
export function isImageOnlyAssistantContent(content: string): boolean {
  const { images, textWithoutImages } = parseMessageImages(content);
  return images.length > 0 && textWithoutImages.trim().length === 0;
}

const REVISION_LEAD_IN =
  /^(?:please\s+)?(?:make it|make them|change (?:it|them)(?:\s+to)?|now|again|instead|try)\s+/i;

const NON_REVISION =
  /^(?:ok|okay|thanks|thank you|yes|no|sure|cool|nice|lol|great|got it|perfect)$/i;

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
  if (!revision || revision.split(/\s+/).length > 8) return null;
  if (NON_IMAGE_SUBJECT.test(revision) || NON_REVISION.test(revision)) return null;
  const cleaned = cleanPrompt(revision);
  if (!cleaned) return null;
  return `${opts.previousSubject}, ${cleaned}`;
}

/** Walk newest→oldest for image-gen context used by revision intercept. */
export function imageGenRevisionContext(
  messages: ReadonlyArray<{ id: string; role: string; content: string }>,
): { lastAssistantIsImageOnly: boolean; previousSubject: string | null } {
  let lastAssistantIsImageOnly = false;
  let previousSubject: string | null = null;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const row = messages[i];
    if (
      row.id === "streaming" ||
      row.id === IMAGE_GEN_PENDING_ASSISTANT_ID ||
      row.id.startsWith("local-")
    ) {
      continue;
    }
    if (!lastAssistantIsImageOnly && row.role === "assistant") {
      lastAssistantIsImageOnly = isImageOnlyAssistantContent(row.content);
      if (!lastAssistantIsImageOnly) {
        // Latest assistant isn't an image — don't treat follow-ups as revisions.
        break;
      }
      continue;
    }
    if (lastAssistantIsImageOnly && row.role === "user") {
      previousSubject = subjectFromImageGenUserMessage(row.content);
      break;
    }
  }
  return { lastAssistantIsImageOnly, previousSubject };
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
 * Short "draw/paint a dog" without an image noun. Anchored full-message only.
 * ``make`` / ``create`` / ``generate`` need an explicit image noun (matchers
 * above) so chat asks like "make your own example" stay in the LLM turn.
 */
const SHORT_DRAW_SUBJECT = new RegExp(
  String.raw`^(?:please\s+)?(?:can you\s+)?` +
    String.raw`(?:draw|paint|illustrate)\s+` +
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

function extractShortDrawSubject(trimmed: string): string | null {
  if (trimmed.length > 80) return null;
  const match = trimmed.match(SHORT_DRAW_SUBJECT);
  if (!match?.[1]) return null;
  const subject = match[1].trim();
  if (subject.split(/\s+/).length > 8) return null;
  if (/^(?:it|them|this|that)\b/i.test(subject)) return null;
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
    if (NON_IMAGE_SUBJECT.test(subject) || NON_IMAGE_DRAW.test(subject)) return null;
    return cleanPrompt(subject);
  }

  const shortDraw = extractShortDrawSubject(trimmed);
  if (shortDraw) return shortDraw;

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
