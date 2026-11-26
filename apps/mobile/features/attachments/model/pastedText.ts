/**
 * Text pasted into the composer, sent as a plain-text file (the composer's side is
 * features/chat/model/composerPaste.ts; attachments.ts writes the file). It is presigned with
 * the purpose "paste", which the API records on the row (apps/api/app/modules/attachments/
 * pasted_text.py) and reads it as it would the same text typed: up to a message's length
 * inline, the rest by retrieval. The name only draws the chip; it never makes a file a paste.
 */
import type { Translate } from "@/lib/i18n/translate";

/** The name a paste's file goes by, drawn as "Pasted text" (the API reads its purpose, not this). */
export const PASTED_TEXT_FILE_NAME = "pasted-text.txt";
export const PASTED_TEXT_CONTENT_TYPE = "text/plain";

/**
 * The most one paste may hold, in characters: what the API keeps a document searchable up
 * to (text_extract.py MAX_INDEX_EXTRACT_CHARS, pasted_text.py PASTED_TEXT_MAX_CHARS).
 */
export const PASTE_MAX_CHARS = 200_000;

/** About this many characters fill a printed page: the limit, told in pages. */
const CHARS_PER_PAGE = 2_000;
export const PASTE_MAX_PAGES = PASTE_MAX_CHARS / CHARS_PER_PAGE;

/** The chip's first words: enough to fill one line, whitespace run together. */
const PREVIEW_SOURCE_CHARS = 200;

/**
 * A composer attachment (attachments.ts PendingAttachment) the composer made from a paste:
 * only `pastedTextAttachment` sets `pasted`. A picked file is never one, whatever its name,
 * as the API reads it (the upload's purpose, never the name).
 */
export function isPastedText(attachment: { fileName: string; pasted?: unknown }): boolean {
  return attachment.pasted != null;
}

/** A file's name as the person reads it: a paste is "Pasted text", in their language. */
export function attachmentDisplayName(fileName: string, t: Translate): string {
  return fileName === PASTED_TEXT_FILE_NAME ? t("chat.pasted_text") : fileName;
}

/** The text's opening words on one line, for the chip. */
export function pastedTextPreview(text: string): string {
  return text.slice(0, PREVIEW_SOURCE_CHARS).replace(/\s+/g, " ").trim();
}
