import type { Message } from "@/lib/api";
import { FOREGROUND_STALE_MS } from "@/lib/foregroundRefresh";

/** A thread as the user left it. */
export type LeftThread = { messages: Message[]; hasMore: boolean; at: number };

const KEPT = 5;

/**
 * Keep the thread the user is leaving. Back within the chat's refresh window
 * (A → B → A), it is shown as it was instead of being read again: its page was
 * read moments ago, and a turn sent since is in it (code-health audit NET-16).
 * The caller keeps none mid-turn.
 */
export function keepLeftThread(threads: Map<string, LeftThread>, chatId: string, thread: LeftThread): void {
  threads.delete(chatId);
  threads.set(chatId, thread);
  while (threads.size > KEPT) threads.delete(threads.keys().next().value as string);
}

/** The thread left moments ago, once; null when there is none or it is too old. */
export function takeRecentLeftThread(
  threads: Map<string, LeftThread>,
  chatId: string,
  now = Date.now(),
): LeftThread | null {
  const thread = threads.get(chatId);
  threads.delete(chatId);
  return thread && now - thread.at < FOREGROUND_STALE_MS.chatMessages ? thread : null;
}
