import { attachmentIdFromRef } from "@/lib/attachmentRef";

const IMAGE_MARKER = /^\[Image:\s*(.+?)\s*\]$/;
const FILE_MARKER = /^\[File:\s*(.+?)\s*\]$/;
const FILE_TYPE_MARKER = /^\[File \(([^)]+)\)\]/;
const FILE_ATTACHED_MARKER = /^\[File attached:/;

const ATTACHMENT_BOILERPLATE = new Set([
  "What's in this image?",
  "Summarize this file.",
]);

export function isAttachmentBoilerplate(text: string): boolean {
  return ATTACHMENT_BOILERPLATE.has(text.trim());
}

export type ParsedMessageImage = {
  attachmentId: string | null;
  path: string;
};

export type ParsedMessageFile = {
  attachmentId: string | null;
  path: string;
  contentType: string | null;
};

export type ParsedUserMessageContent = {
  caption: string;
  images: ParsedMessageImage[];
  files: ParsedMessageFile[];
  hasFileAttachment: boolean;
};

export function parseUserMessageContent(content: string): ParsedUserMessageContent {
  const images: ParsedMessageImage[] = [];
  const files: ParsedMessageFile[] = [];
  const captionLines: string[] = [];
  let hasFileAttachment = false;
  let pendingFileType: string | null = null;
  let inFileExcerpt = false;

  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (!inFileExcerpt) captionLines.push(line);
      continue;
    }

    const imageMatch = trimmed.match(IMAGE_MARKER);
    if (imageMatch) {
      inFileExcerpt = false;
      const ref = imageMatch[1].trim();
      images.push({
        attachmentId: attachmentIdFromRef(ref),
        path: ref,
      });
      continue;
    }

    const fileMatch = trimmed.match(FILE_MARKER);
    if (fileMatch) {
      inFileExcerpt = false;
      const ref = fileMatch[1].trim();
      files.push({
        attachmentId: attachmentIdFromRef(ref),
        path: ref,
        contentType: pendingFileType,
      });
      pendingFileType = null;
      hasFileAttachment = true;
      continue;
    }

    const fileTypeMatch = trimmed.match(FILE_TYPE_MARKER);
    if (fileTypeMatch) {
      const type = fileTypeMatch[1].trim().toLowerCase();
      if (files.length > 0) {
        files[files.length - 1].contentType = type;
      } else {
        pendingFileType = type;
      }
      hasFileAttachment = true;
      inFileExcerpt = true;
      continue;
    }

    if (FILE_ATTACHED_MARKER.test(trimmed)) {
      hasFileAttachment = true;
      continue;
    }

    if (inFileExcerpt) continue;

    captionLines.push(line);
  }

  const caption = captionLines.join("\n").trim();
  const visibleCaption =
    (images.length > 0 || files.length > 0) && isAttachmentBoilerplate(caption) ? "" : caption;
  return { caption: visibleCaption, images, files, hasFileAttachment };
}

/** Extract inline `[Image: …]` markers from any message role. */
export function parseMessageImages(content: string): {
  images: ParsedMessageImage[];
  textWithoutImages: string;
} {
  const images: ParsedMessageImage[] = [];
  const kept: string[] = [];
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    const imageMatch = trimmed.match(IMAGE_MARKER);
    if (imageMatch) {
      const ref = imageMatch[1].trim();
      images.push({
        attachmentId: attachmentIdFromRef(ref),
        path: ref,
      });
      continue;
    }
    kept.push(line);
  }
  return { images, textWithoutImages: kept.join("\n").trim() };
}

export function userMessageHasImage(content: string, localImageUri?: string | null): boolean {
  if (localImageUri) return true;
  return parseUserMessageContent(content).images.length > 0;
}

export function isPdfContentType(contentType: string | null | undefined): boolean {
  return (contentType ?? "").split(";")[0].trim().toLowerCase() === "application/pdf";
}

export function guessFileNameFromCaption(caption: string, fallback = "document.pdf"): string {
  const trimmed = caption.trim();
  if (!trimmed) return fallback;
  if (/\.[a-z0-9]{2,5}$/i.test(trimmed) && !trimmed.includes("\n")) return trimmed;
  return fallback;
}
