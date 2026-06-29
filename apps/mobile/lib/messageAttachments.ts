const IMAGE_MARKER = /^\[Image:\s*(.+?)\s*\]$/;
const FILE_MARKER = /^\[File(?:\s|\()/;
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

export type ParsedUserMessageContent = {
  caption: string;
  images: ParsedMessageImage[];
  hasFileAttachment: boolean;
};

export function parseUserMessageContent(content: string): ParsedUserMessageContent {
  const images: ParsedMessageImage[] = [];
  const captionLines: string[] = [];
  let hasFileAttachment = false;

  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) {
      captionLines.push(line);
      continue;
    }

    const imageMatch = trimmed.match(IMAGE_MARKER);
    if (imageMatch) {
      const ref = imageMatch[1].trim();
      const idMatch = ref.match(/\/attachments\/([0-9a-f-]{36})\/file/i);
      images.push({
        attachmentId: idMatch?.[1] ?? null,
        path: ref,
      });
      continue;
    }

    if (FILE_MARKER.test(trimmed) || FILE_ATTACHED_MARKER.test(trimmed)) {
      hasFileAttachment = true;
      continue;
    }

    captionLines.push(line);
  }

  const caption = captionLines.join("\n").trim();
  const visibleCaption =
    images.length > 0 && isAttachmentBoilerplate(caption) ? "" : caption;
  return { caption: visibleCaption, images, hasFileAttachment };
}

export function userMessageHasImage(content: string, localImageUri?: string | null): boolean {
  if (localImageUri) return true;
  return parseUserMessageContent(content).images.length > 0;
}
