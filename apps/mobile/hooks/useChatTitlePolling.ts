import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { getCachedChat, peekCreatedChat } from "@/lib/cache/chatListCache";
import { chatNeedsGeneratedTitle } from "@/lib/chat/chatTitle";
import { firstReplyTitlePlan } from "@/lib/chatTitleRefresh";
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
  getFirstUserText?: () => string | undefined;
};

const TITLE_POLL_ATTEMPTS = 8;
const TITLE_POLL_MS = 2000;

/** Polls for the auto-generated chat title after the first assistant reply. */
export function useChatTitlePolling({
  token,
  chatId,
  setChatTitle,
  getFirstUserText,
}: Options) {
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
        for (let i = 0; i < TITLE_POLL_ATTEMPTS; i++) {
          await new Promise((r) => setTimeout(r, TITLE_POLL_MS));
          try {
            const updated = await api.getChat(tid, cid);
            if (updated.title && !chatNeedsGeneratedTitle(updated.title)) {
              patchChatGlobal(cid, { title: updated.title });
              // Header follows the open chat only. Drawer patch still applies
              // after New chat / another thread (the topic job is for `cid`).
              if (cid === chatIdRef.current) {
                setChatTitle(updated.title);
              }
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

  const handleFirstReply = useCallback(async (explicitChatId?: string | null) => {
    const cid = explicitChatId ?? chatId;
    if (!token || !cid) return;
    const plan = firstReplyTitlePlan(
      peekCreatedChat(cid),
      getCachedChat(cid),
      getFirstUserText?.(),
    );
    let shouldPoll = plan.poll;
    if (plan.insert) {
      insertChatGlobal(plan.insert);
      if (plan.insert.title && !chatNeedsGeneratedTitle(plan.insert.title)) {
        setChatTitle(plan.insert.title);
      }
    } else if (plan.fetch) {
      try {
        const chat = await api.getChat(token, cid);
        insertChatGlobal(chat);
        if (chat.title && !chatNeedsGeneratedTitle(chat.title)) {
          setChatTitle(chat.title);
          shouldPoll = false;
        }
      } catch {
        /* drawer insert is best-effort */
      }
    }
    if (shouldPoll) {
      await pollForTitle(token, cid);
    }
  }, [token, chatId, pollForTitle, setChatTitle, getFirstUserText]);

  useEffect(() => {
    setTitleGenerating(false);
    if (!chatId) {
      setChatTitleGenerating(null);
    }
  }, [chatId]);

  return { titleGenerating, pollForTitle, handleFirstReply };
}
