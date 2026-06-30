import { useEffect } from "react";

import { shouldPreCreateDraft, shouldWarmDraftSocket } from "@/lib/chatDraftLogic";

type Options = {
  token: string | null;
  routeChatId: string | undefined;
  chatId: string | null;
  messagesLength: number;
  streaming: boolean;
  draftChatId: string | null;
  prepareDraftChat: (projectId?: string | null) => Promise<string | null>;
  connect: () => void | Promise<void>;
};

export function useChatDraftWarmup({
  token,
  routeChatId,
  chatId,
  messagesLength,
  streaming,
  draftChatId,
  prepareDraftChat,
  connect,
}: Options) {
  useEffect(() => {
    if (
      !shouldPreCreateDraft({
        token,
        routeChatId,
        chatId,
        messagesLength,
        streaming,
      })
    ) {
      return;
    }
    void prepareDraftChat();
  }, [token, routeChatId, chatId, messagesLength, streaming, prepareDraftChat]);

  useEffect(() => {
    if (!shouldWarmDraftSocket({ token, draftChatId, chatId, streaming })) return;
    void connect();
  }, [token, draftChatId, chatId, streaming, connect]);
}
