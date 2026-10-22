import { useEffect } from "react";

import type { Message } from "@/lib/api";
import { getCachedChat } from "@/lib/cache/chatListCache";
import {
  isSettledThread,
  keepCachedChatPage,
  markCachedChatPageStale,
} from "@/features/chat/model/messageCache";

/** The server read the shown thread rests on; none until this open's read lands. */
export type ChatPageSync = {
  chatId: string;
  fetchedAt: number;
};

type Options = {
  chatId: string | null;
  /** The chat the route names; while it differs from `chatId` the view is between two chats. */
  routeChatId: string | undefined;
  messages: Message[];
  /** A reply is streaming or finalizing. */
  busy: boolean;
  hasMoreOlder: boolean;
  sync: ChatPageSync | null;
};

/**
 * Keeps the open chat's page in step with what it shows: each finished turn,
 * follow-up questions, feedback or edit is kept once the thread settles, so
 * the next open paints it at once. Until then the kept page is marked stale and
 * the next open reads the chat.
 */
export function useChatPageCacheWriter({ chatId, routeChatId, messages, busy, hasMoreOlder, sync }: Options) {
  useEffect(() => {
    if (!chatId || chatId !== routeChatId) return;
    if (busy || sync?.chatId !== chatId || !isSettledThread(messages)) {
      markCachedChatPageStale(chatId);
      return;
    }
    keepCachedChatPage(chatId, messages, hasMoreOlder, sync.fetchedAt, getCachedChat(chatId)?.updated_at);
  }, [chatId, routeChatId, messages, busy, hasMoreOlder, sync]);
}
