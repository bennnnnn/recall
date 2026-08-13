import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import {
  insertChatGlobal,
  isChatTitleGenerating,
  patchChatGlobal,
  setChatTitleGenerating,
} from "@/lib/drawer";

type Options = {
  token: string | null;
  chatId: string | null;
  setChatTitle: (title: string | null) => void;
};

/** Polls for the auto-generated chat title after the first assistant reply. */
export function useChatTitlePolling({ token, chatId, setChatTitle }: Options) {
  const [titleGenerating, setTitleGenerating] = useState(false);
  const chatIdRef = useRef(chatId);
  chatIdRef.current = chatId;

  const pollForTitle = useCallback(
    async (tid: string, cid: string) => {
      setChatTitleGenerating(cid);
      if (cid === chatIdRef.current) {
        setTitleGenerating(true);
      }
      try {
        for (let i = 0; i < 5; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          if (cid !== chatIdRef.current) return;
          try {
            const updated = await api.getChat(tid, cid);
            if (updated.title) {
              if (cid !== chatIdRef.current) return;
              setChatTitle(updated.title);
              patchChatGlobal(cid, { title: updated.title });
              return;
            }
          } catch {
            /* ignore */
          }
        }
      } finally {
        if (cid === chatIdRef.current) {
          setTitleGenerating(false);
        }
        // Single-slot marker: only drop it if this poll still owns it. A's
        // poll ending after we opened B must not clear B's generating state.
        if (isChatTitleGenerating(cid)) {
          setChatTitleGenerating(null);
        }
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
    setTitleGenerating(false);
    if (!chatId) {
      setChatTitleGenerating(null);
    }
  }, [chatId]);

  return { titleGenerating, pollForTitle, handleFirstReply };
}
