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

const NON_IMAGE_DRAW = new RegExp(
  String.raw`\b(?:conclusion|inference|boundary|line|diagram|chart|graph|plot|sketch\s+of\s+the\s+idea)\b`,
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
