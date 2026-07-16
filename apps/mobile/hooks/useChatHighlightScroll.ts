import { useCallback, useEffect, useRef, useState } from "react";
import type { FlashListRef } from "@shopify/flash-list";
import { useRouter } from "expo-router";

type Router = ReturnType<typeof useRouter>;

import type { Message } from "@/lib/api";

type Options = {
  routeHighlightMessage: string | undefined;
  router: Router;
  messages: Message[];
  hasMoreOlder: boolean;
  loadingOlder: boolean;
  token: string | null;
  chatId: string | null;
  loadOlderMessages: () => Promise<void>;
  listRef: React.RefObject<FlashListRef<Message> | null>;
};

/** Deep-link message highlight: scrolls a route-provided message id into view, paging in older messages if it isn't loaded yet. */
export function useChatHighlightScroll({
  routeHighlightMessage,
  router,
  messages,
  hasMoreOlder,
  loadingOlder,
  token,
  chatId,
  loadOlderMessages,
  listRef,
}: Options) {
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(null);
  const pendingHighlightRef = useRef<string | null>(null);
  const highlightLoadInFlightRef = useRef(false);

  useEffect(() => {
    if (typeof routeHighlightMessage === "string" && routeHighlightMessage) {
      pendingHighlightRef.current = routeHighlightMessage;
      setHighlightedMessageId(routeHighlightMessage);
      router.setParams({ highlightMessage: undefined });
    }
  }, [routeHighlightMessage, router]);

  const tryScrollToHighlight = useCallback(async () => {
    const targetId = pendingHighlightRef.current;
    if (!targetId || messages.length === 0) return;
    const index = messages.findIndex((m) => m.id === targetId);
    if (index >= 0) {
      pendingHighlightRef.current = null;
      requestAnimationFrame(() => {
        listRef.current?.scrollToIndex({
          index,
          animated: true,
          viewPosition: 0.5,
        });
      });
      setTimeout(() => setHighlightedMessageId(null), 3500);
      return;
    }
    if (hasMoreOlder && !loadingOlder && !highlightLoadInFlightRef.current && token && chatId) {
      highlightLoadInFlightRef.current = true;
      try {
        await loadOlderMessages();
      } finally {
        highlightLoadInFlightRef.current = false;
      }
    }
  }, [messages, hasMoreOlder, loadingOlder, token, chatId, loadOlderMessages, listRef]);

  useEffect(() => {
    void tryScrollToHighlight();
  }, [tryScrollToHighlight]);

  return { highlightedMessageId };
}
