import { useCallback, useRef, useState } from "react";

import { api } from "@/lib/api";
import { resolveActiveChatId } from "@/lib/chatDraftLogic";

type Options = {
  token: string | null;
  chatId: string | null;
};

export function useDraftChat({ token, chatId }: Options) {
  const [draftChatId, setDraftChatId] = useState<string | null>(null);
  const draftChatIdRef = useRef<string | null>(null);
  const draftProjectIdRef = useRef<string | null>(null);
  const draftCreatePromiseRef = useRef<Promise<string | null> | null>(null);
  const skipLoadForChatIdRef = useRef<string | null>(null);
  const creatingRef = useRef(false);

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
      draftProjectIdRef.current = null;
      draftCreatePromiseRef.current = null;
      setDraftChatId(null);
      if (toDiscard && token) {
        api.deleteChat(token, toDiscard).catch(() => {});
      }
    },
    [token],
  );

  const prepareDraftChat = useCallback(
    async (projectId?: string | null, model = "auto"): Promise<string | null> => {
      if (!token) return null;
      if (chatId) return chatId;
      if (draftChatIdRef.current) return draftChatIdRef.current;
      if (draftCreatePromiseRef.current) return draftCreatePromiseRef.current;

      const resolvedProjectId = projectId ?? draftProjectIdRef.current ?? undefined;
      if (resolvedProjectId) {
        draftProjectIdRef.current = resolvedProjectId;
      }

      const task = api
        .createChat(token, model, resolvedProjectId)
        .then((chat) => {
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

  return {
    draftChatId,
    setDraftChatId,
    draftChatIdRef,
    draftProjectIdRef,
    draftCreatePromiseRef,
    skipLoadForChatIdRef,
    creatingRef,
    discardEmptyChat,
    clearDraftChat,
    prepareDraftChat,
    activeChatId: resolveActiveChatId(chatId, draftChatId),
  };
}
