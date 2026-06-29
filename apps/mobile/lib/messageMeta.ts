import type { Message } from "@/lib/api";

/** Memory-recall chip — only on fresh assistant replies (not reloaded history). */
export function shouldShowRecalledChip(
  message: Pick<Message, "role" | "recalled">,
  options: { isStreaming: boolean; isLastAssistant: boolean },
): boolean {
  if (message.role !== "assistant") return false;
  if (options.isStreaming) return false;
  if (!options.isLastAssistant) return false;
  return (message.recalled ?? 0) > 0;
}

export function recalledMemoryCount(message: Pick<Message, "recalled">): number {
  return Math.max(0, message.recalled ?? 0);
}
