import type { Message } from "@/lib/api";
import { messageTextForSend, type PendingAttachment } from "@/lib/attachments";

export function shouldBlockSend(options: {
  text: string;
  hasAttachment: boolean;
  streaming: boolean;
  token: string | null;
  creating: boolean;
  attachBusy: boolean;
}): boolean {
  const trimmed = options.text.trim();
  if (!trimmed && !options.hasAttachment) return true;
  if (options.streaming || !options.token || options.creating || options.attachBusy) {
    return true;
  }
  return false;
}

export function buildOptimisticUserMessage(options: {
  text: string;
  attached: PendingAttachment | null;
  optimisticId: string;
  createdAt: string;
}): Message {
  const sendText = messageTextForSend(options.text, options.attached);
  const display =
    options.text.trim() ||
    (options.attached?.kind === "file" ? options.attached.fileName : sendText);
  return {
    id: options.optimisticId,
    role: "user",
    content: display,
    model: null,
    local_image_uri:
      options.attached?.kind === "image" ? options.attached.localUri : null,
    created_at: options.createdAt,
  };
}

import type { ClientGeo } from "@/lib/clientGeo";

export function buildPendingSendAfterCreate(options: {
  text: string;
  attached: PendingAttachment | null;
  attachmentIds?: string[];
  optimisticId: string;
  clientGeo?: ClientGeo | null;
}): {
  text: string;
  skipUserBubble: true;
  trackSendingMessageId: string;
  attachmentIds?: string[];
  localImageUri?: string | null;
  clientGeo?: ClientGeo | null;
} {
  const sendText = messageTextForSend(options.text, options.attached);
  return {
    text: sendText,
    skipUserBubble: true,
    trackSendingMessageId: options.optimisticId,
    attachmentIds: options.attachmentIds,
    localImageUri:
      options.attached?.kind === "image" ? options.attached.localUri : null,
    clientGeo: options.clientGeo ?? null,
  };
}
