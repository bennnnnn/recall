import { parseMessageImages } from "@/lib/messageAttachments";

/** The assistant row a generating picture paints, and the one it becomes on failure. */
export const IMAGE_GEN_PENDING_ASSISTANT_ID = "image-gen-pending";
export const IMAGE_GEN_FAILED_ASSISTANT_ID = "image-gen-failed";

/** True when the assistant bubble is only an `[Image: …]` marker (no prose). */
export function isImageOnlyAssistantContent(content: string): boolean {
  const { images, textWithoutImages } = parseMessageImages(content);
  return images.length > 0 && textWithoutImages.trim().length === 0;
}
