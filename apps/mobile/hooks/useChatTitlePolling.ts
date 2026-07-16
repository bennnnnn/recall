import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { insertChatGlobal, patchChatGlobal, setChatTitleGenerating } from "@/lib/drawer";

type Options = {
  token: string | null;
  chatId: string | null;
  setChatTitle: (title: string | null) => void;
};

/** Polls for the auto-generated chat title after the first assistant reply. */
export function useChatTitlePolling({ token, chatId, setChatTitle }: Options) {
  const [titleGenerating, setTitleGenerating] = useState(false);

  const pollForTitle = useCallback(
    async (tid: string, cid: string) => {
      setTitleGenerating(true);
      setChatTitleGenerating(cid);
      try {
        for (let i = 0; i < 5; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          try {
            const updated = await api.getChat(tid, cid);
            if (updated.title) {
              setChatTitle(updated.title);
              patchChatGlobal(cid, { title: updated.title });
              return;
            }
          } catch {
            /* ignore */
          }
        }
      } finally {
        setTitleGenerating(false);
        setChatTitleGenerating(null);
      }
    },
    [setChatTitle],
  );

  const handleFirstReply = useCallback(async () => {
    if (!token || !chatId) return;
    try {
      const chat = await api.getChat(token, chatId);
      insertChatGlobal(chat);
    } catch {
      /* drawer insert is best-effort */
    }
    await pollForTitle(token, chatId);
  }, [token, chatId, pollForTitle]);

  useEffect(() => {
    if (!chatId) {
      setTitleGenerating(false);
      setChatTitleGenerating(null);
    }
  }, [chatId]);

  return { titleGenerating, pollForTitle, handleFirstReply };
}
