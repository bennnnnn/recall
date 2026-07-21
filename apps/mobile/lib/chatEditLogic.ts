import type { Message } from "@/lib/api";

/** Truncate the thread at *messageId* and replace that turn with the edited text. */
export function applyOptimisticEdit(
  messages: Message[],
  messageId: string,
  content: string,
  localId: string,
): { snapshot: Message[]; messages: Message[] } {
  const index = messages.findIndex((m) => m.id === messageId);
  if (index < 0) {
    return { snapshot: messages, messages };
  }
  return {
    snapshot: messages,
    messages: [
      ...messages.slice(0, index),
      {
        id: localId,
        role: "user",
        content: content.trim(),
        model: null,
        created_at: new Date().toISOString(),
      },
    ],
  };
}

/** Prefer restoring an in-flight edit snapshot over regenerate/partial keep. */
export function shouldRestoreEditOnError(hasEditBackup: boolean): boolean {
  return hasEditBackup;
}
