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

/**
 * Content of the user message immediately before `messages[index]`, when that
 * item is the assistant's reply to it — otherwise null. Computed once per row
 * by the list (which already has the full array) so row components can take
 * a plain string prop instead of the whole `messages` array; passing the full
 * array as a row prop defeats React.memo, since any new message anywhere in
 * the chat produces a new array reference and re-renders every row.
 */
export function priorUserTextFor(messages: Message[], index: number): string | null {
  const item = messages[index];
  if (!item || item.role !== "assistant" || index <= 0) return null;
  const prior = messages[index - 1];
  return prior?.role === "user" ? prior.content : null;
}

/** True while tokens are streaming or the server is persisting after stream_end. */
export function isChatStreamActive(streaming: boolean, finalizing: boolean): boolean {
  return streaming || finalizing;
}

/**
 * Whether a row's own rendered output depends on the current stream state —
 * true for every user message (editing is locked for the whole chat while any
 * turn is in flight) and for the single row matching lastAssistantId (gates
 * the regenerate button). Every other assistant row returns a stable `false`
 * regardless of streaming/finalizing, so passing this instead of the raw
 * booleans means React.memo sees no prop change for those rows when a turn
 * starts or ends, instead of re-rendering the entire historical list twice
 * per turn for state none of those rows actually use.
 */
export function streamVisualActiveForRow(
  role: Message["role"],
  itemId: string,
  lastAssistantId: string | null,
  streaming: boolean,
  finalizing: boolean,
): boolean {
  const isLastAssistant = role === "assistant" && itemId === lastAssistantId;
  if (role !== "user" && !isLastAssistant) return false;
  return isChatStreamActive(streaming, finalizing);
}
