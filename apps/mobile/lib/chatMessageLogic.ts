import { Message } from "@/lib/api";

export const SENDING_LABEL_DELAY_MS = 400;

export function isLocalPendingMessageId(id: string): boolean {
  return id.startsWith("local-");
}

export function findLastLocalUserMessageId(messages: Message[]): string | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message.role === "user" && isLocalPendingMessageId(message.id)) {
      return message.id;
    }
  }
  return null;
}

export function findLastAssistantId(messages: Message[]): string | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") return messages[i].id;
  }
  return null;
}
