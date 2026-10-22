import { useCallback, useRef, useState } from "react";

import type { IconName } from "@/ui/icons/names";

import { api, type Message } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { isServerMessageId } from "@/lib/serverMessageId";
import { MESSAGE_PAGE_SIZE } from "@/features/chat/model/constants";

type Options = {
  token: string | null;
  chatId: string | null;
  chatLoading: boolean;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  /** The route loader's view; a page asked for by an earlier view is dropped. */
  viewRef: { readonly current: { version: number } };
  isActiveChat: (chatId: string) => boolean;
  showActionBanner: (message: string, icon?: IconName) => void;
  t: (key: string) => string;
};

/** "Load earlier": one page before the oldest saved row, at most one request at a time. */
export function useChatOlderMessages({
  token,
  chatId,
  chatLoading,
  messages,
  setMessages,
  viewRef,
  isActiveChat,
  showActionBanner,
  t,
}: Options) {
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const olderRequestRef = useRef<object | null>(null);
  const session = getSessionGeneration();
  const viewVersion = viewRef.current.version;

  /** A new view: forget the page still loading for the last one. */
  const resetOlder = useCallback(() => {
    olderRequestRef.current = null;
    setLoadingOlder(false);
  }, []);

  const loadOlderMessages = useCallback(async () => {
    if (
      !token || !chatId || session !== getSessionGeneration() || viewVersion !== viewRef.current.version ||
      !isActiveChat(chatId) || chatLoading || olderRequestRef.current ||
      !hasMoreOlder || messages.length === 0
    ) return;
    const oldest = messages[0];
    if (!isServerMessageId(oldest.id)) return;

    const request = {};
    const version = viewRef.current.version;
    const ownerSession = getSessionGeneration();
    const isCurrent = () =>
      ownerSession === getSessionGeneration() && version === viewRef.current.version && olderRequestRef.current === request;
    olderRequestRef.current = request;
    setLoadingOlder(true);
    try {
      const page = await api.listMessages(token, chatId, {
        limit: MESSAGE_PAGE_SIZE,
        before: oldest.id,
      });
      if (!isCurrent()) return;
      setMessages((prev) => {
        if (ownerSession !== getSessionGeneration() || version !== viewRef.current.version) return prev;
        const knownIds = new Set(prev.map((message) => message.id));
        return [...page.messages.filter((message) => !knownIds.has(message.id)), ...prev];
      });
      setHasMoreOlder(page.has_more);
    } catch {
      if (isCurrent()) showActionBanner(t("common.error"), "alert-circle");
    } finally {
      if (isCurrent()) {
        olderRequestRef.current = null;
        setLoadingOlder(false);
      }
    }
  }, [
    token, session, viewVersion, viewRef, chatId, isActiveChat, chatLoading, hasMoreOlder, messages, setMessages,
    showActionBanner, t,
  ]);

  return { hasMoreOlder, setHasMoreOlder, loadingOlder, loadOlderMessages, resetOlder };
}
