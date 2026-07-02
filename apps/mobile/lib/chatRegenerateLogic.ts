import type { Message } from "@/lib/api";

/** Remove the last assistant turn for regenerate; keep a copy to restore on failure. */
export function popLastAssistantMessage(messages: Message[]): {
  backup: Message | null;
  messages: Message[];
} {
  const next = [...messages];
  const last = next[next.length - 1];
  if (last?.role !== "assistant") {
    return { backup: null, messages: next };
  }
  next.pop();
  return { backup: last, messages: next };
}

/** Put back the prior assistant reply when regenerate fails before a replacement. */
export function restoreAssistantMessage(
  messages: Message[],
  backup: Message | null,
): Message[] {
  if (!backup) return messages;
  if (messages.some((m) => m.id === backup.id)) return messages;
  return [...messages, backup];
}
