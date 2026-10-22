import { useEffect } from "react";

import { useAccountSession } from "@/contexts/accountSession";
import { shouldWarmDraftSocket } from "@/features/chat/model/draftLogic";

type Options = {
  chatId: string | null;
  streaming: boolean;
  draftChatId: string | null;
  connect: () => void | Promise<void>;
};

/** Open the draft chat's socket once the draft exists: the user has started writing. */
export function useChatDraftWarmup({ chatId, streaming, draftChatId, connect }: Options) {
  const { account } = useAccountSession();
  useEffect(() => {
    if (!shouldWarmDraftSocket({ account, draftChatId, chatId, streaming })) return;
    void connect();
  }, [account, draftChatId, chatId, streaming, connect]);
}
