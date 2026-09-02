import type { Message } from "@/lib/api/types";

export type LiveTalkSpeakEvent =
  | { type: "user"; text: string }
  | { type: "assistant"; text: string }
  | {
      type: "done";
      remaining: number;
      limit: number;
      user_message: Message | null;
      assistant_message: Message | null;
    };

export function liveTalkLocalIds(turnId: string): { user: string; assistant: string } {
  return {
    user: `local-live-user-${turnId}`,
    assistant: `local-live-assistant-${turnId}`,
  };
}

function upsertLiveTalkMessage(
  messages: Message[],
  id: string,
  role: "user" | "assistant",
  content: string,
  model: string | null,
): Message[] {
  const index = messages.findIndex((row) => row.id === id);
  if (index >= 0) {
    const next = messages.slice();
    next[index] = { ...next[index], content };
    return next;
  }
  return [
    ...messages,
    {
      id,
      role,
      content,
      model,
      created_at: new Date().toISOString(),
    },
  ];
}

export function dropLiveTalkLocalTurn(messages: Message[], turnId: string): Message[] {
  const ids = liveTalkLocalIds(turnId);
  return messages.filter((row) => row.id !== ids.user && row.id !== ids.assistant);
}

export function applyLiveTalkChatEvent(
  messages: Message[],
  turnId: string,
  event: LiveTalkSpeakEvent,
): Message[] {
  const ids = liveTalkLocalIds(turnId);
  if (event.type === "user" && event.text.trim()) {
    return upsertLiveTalkMessage(messages, ids.user, "user", event.text, null);
  }
  if (event.type === "assistant" && event.text.trim()) {
    return upsertLiveTalkMessage(
      messages,
      ids.assistant,
      "assistant",
      event.text,
      "live-talk-model",
    );
  }
  if (event.type !== "done") return messages;
  const without = messages.filter((row) => row.id !== ids.user && row.id !== ids.assistant);
  const next = [...without];
  if (event.user_message) next.push(event.user_message);
  else {
    const local = messages.find((row) => row.id === ids.user);
    if (local) next.push(local);
  }
  if (event.assistant_message) next.push(event.assistant_message);
  else {
    const local = messages.find((row) => row.id === ids.assistant);
    if (local) next.push(local);
  }
  return next;
}
