import type { Message } from "@/lib/api";
import type { StreamingDraft } from "@/lib/streamingDraftStore";

export function replaceStreamingMessageWithPartial(
  messages: Message[],
  partial: string,
  draft: StreamingDraft | null,
  id: string,
): Message[] {
  return messages.map((message) =>
    message.id === "streaming"
      ? {
          ...message,
          id,
          content: partial,
          search_sources: draft?.search_sources ?? message.search_sources,
          generationStopped: true,
        }
      : message,
  );
}
