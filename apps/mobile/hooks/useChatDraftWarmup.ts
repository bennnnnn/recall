import { useEffect } from "react";

import { shouldWarmDraftSocket } from "@/lib/chatDraftLogic";

type Options = {
  token: string | null;
  chatId: string | null;
  streaming: boolean;
  draftChatId: string | null;
  connect: () => void | Promise<void>;
};

export function useChatDraftWarmup({
  token,
  chatId,
  streaming,
  draftChatId,
  connect,
}: Options) {
  useEffect(() => {
    if (!shouldWarmDraftSocket({ token, draftChatId, chatId, streaming })) return;
    void connect();
  }, [token, draftChatId, chatId, streaming, connect]);
}
