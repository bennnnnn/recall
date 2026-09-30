import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { rememberCreatedChat } from "@/lib/cache/chatListCache";
import { resolveActiveChatId } from "@/lib/chat/draftLogic";

const DRAFT_PREWARM_DELAY_MS = 125;

type Options = {
  token: string | null;
  chatId: string | null;
};

export function useDraftChat({ token, chatId }: Options) {
  const [draftChatId, setDraftChatId] = useState<string | null>(null);
  const draftChatIdRef = useRef<string | null>(null);
  const draftCreatePromiseRef = useRef<Promise<string | null> | null>(null);
  const skipLoadForChatIdRef = useRef<string | null>(null);
  const creatingRef = useRef(false);
  const chatIdRef = useRef(chatId);
  chatIdRef.current = chatId;

  const discardEmptyChat = useCallback(
    (id: string | null) => {
      if (!token || !id) return;
      api.deleteChatIfEmpty(token, id).catch(() => {});
    },
    [token],
  );

  const clearDraftChat = useCallback(
    (id?: string | null) => {
      const toDiscard = id ?? draftChatIdRef.current;
      draftChatIdRef.current = null;
      draftCreatePromiseRef.current = null;
      setDraftChatId(null);
      if (toDiscard && token) {
        api.deleteChat(token, toDiscard).catch(() => {});
      }
    },
    [token],
  );

  const prepareDraftChat = useCallback(
    async (model = "auto", opts?: { force?: boolean }): Promise<string | null> => {
      if (!token) return null;
      if (opts?.force) {
        draftChatIdRef.current = null;
        setDraftChatId(null);
      }
      if (chatId && !opts?.force) return chatId;
      if (draftChatIdRef.current && !opts?.force) return draftChatIdRef.current;
      if (draftCreatePromiseRef.current) return draftCreatePromiseRef.current;

      const task = api
        .createChat(token, model)
        .then((chat) => {
          rememberCreatedChat(chat);
          draftChatIdRef.current = chat.id;
          setDraftChatId(chat.id);
          return chat.id;
        })
        .catch(() => null)
        .finally(() => {
          draftCreatePromiseRef.current = null;
        });
      draftCreatePromiseRef.current = task;
      return task;
    },
    [token, chatId],
  );

  // Hide the first-message create-chat round trip behind the time the user
  // spends looking at / typing into a fresh conversation. Delay one beat so an
  // existing route can synchronously claim chatId first; the ref check avoids
  // creating a throwaway draft while chat history is opening.
  useEffect(() => {
    if (!token || chatId || draftChatIdRef.current || draftCreatePromiseRef.current) return;
    const timer = setTimeout(() => {
      if (chatIdRef.current || draftChatIdRef.current || draftCreatePromiseRef.current) return;
      void prepareDraftChat();
    }, DRAFT_PREWARM_DELAY_MS);
    return () => clearTimeout(timer);
  }, [token, chatId, prepareDraftChat]);

  return {
    draftChatId,
    setDraftChatId,
    draftChatIdRef,
    draftCreatePromiseRef,
    skipLoadForChatIdRef,
    creatingRef,
    discardEmptyChat,
    clearDraftChat,
    prepareDraftChat,
    activeChatId: resolveActiveChatId(chatId, draftChatId),
  };
}
