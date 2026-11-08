import type { Message } from "@/lib/api/types";

export type LiveTalkSpeakEvent =
  | { type: "user"; text: string }
  | { type: "assistant"; text: string; sources?: Message["search_sources"] }
  | {
      type: "done";
      remaining: number;
      limit: number;
      user_message: Message | null;
      assistant_message: Message | null;
    };

function liveTalkLocalIds(turnId: string): { user: string; assistant: string } {
  return {
    user: `local-live-user-${turnId}`,
    assistant: `local-live-assistant-${turnId}`,
  };
}

/** A new row goes last, or just above the row `beforeId` names when it is there. */
function upsertLiveTalkMessage(
  messages: Message[],
  id: string,
  role: "user" | "assistant",
  content: string,
  model: string | null,
  beforeId?: string,
): Message[] {
  const index = messages.findIndex((row) => row.id === id);
  if (index >= 0) {
    const next = messages.slice();
    next[index] = { ...next[index], content };
    return next;
  }
  const row: Message = { id, role, content, model, created_at: new Date().toISOString() };
  const before = beforeId ? messages.findIndex((existing) => existing.id === beforeId) : -1;
  if (before < 0) return [...messages, row];
  return [...messages.slice(0, before), row, ...messages.slice(before)];
}

export function applyLiveTalkChatEvent(
  messages: Message[],
  turnId: string,
  event: LiveTalkSpeakEvent,
): Message[] {
  const ids = liveTalkLocalIds(turnId);
  if (event.type === "user" && event.text.trim()) {
    // The user's line is transcribed beside the reply and often lands after it: it goes
    // above the reply it prompted, never below it.
    return upsertLiveTalkMessage(messages, ids.user, "user", event.text, null, ids.assistant);
  }
  if (event.type === "assistant" && event.text.trim()) {
    return upsertLiveTalkMessage(
      messages,
      ids.assistant,
      "assistant",
      event.text,
      "live-talk-model",
    ).map((row) => row.id === ids.assistant && event.sources ? { ...row, search_sources: event.sources } : row);
  }
  if (event.type !== "done") return messages;
  // A late persistence response must replace its placeholders where they
  // already are, not move an old turn below the next live utterance.
  if (event.user_message || event.assistant_message) {
    return messages.flatMap((row) => {
      if (row.id === ids.user) return event.user_message ? [event.user_message] : [row];
      if (row.id === ids.assistant) return event.assistant_message ? [event.assistant_message] : [row];
      return [row];
    });
  }
  return messages;
}
