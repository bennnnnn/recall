import { useCallback, useEffect, useRef, useState } from "react";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { useAuth } from "@/contexts/AuthContext";
import { useChat } from "@/hooks/useChat";
import { api } from "@/lib/api";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

/** Live chat for one automation's dedicated thread — the same WS/SSE
 * streaming engine as the main chat screen (`useChat`), scoped to an
 * already-existing chat id with none of the home screen's draft-chat /
 * starters / quiz / attachments baggage. Seeds history once via
 * `listAllMessages`, then `useChat` owns send/stream/regenerate. */
export function useAutomationChat(chatId: string | null, isCurrent: () => boolean) {
  const { token } = useAuth();
  const feedback = useActionFeedbackOptional();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const seededChatId = useRef<string | null>(null);

  const onError = useCallback(
    (message: string) => {
      if (isCurrent()) reportRecoverableError(feedback, message);
    },
    [isCurrent, feedback],
  );

  const chat = useChat(token, chatId, { onError });
  const { setMessages } = chat;

  useEffect(() => {
    if (!token || !chatId || seededChatId.current === chatId) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(false);
    void api
      .listAllMessages(token, chatId)
      .then((rows) => {
        if (cancelled || !isCurrent()) return;
        seededChatId.current = chatId;
        setMessages(rows);
      })
      .catch(() => {
        if (!cancelled && isCurrent()) setLoadError(true);
      })
      .finally(() => {
        if (!cancelled && isCurrent()) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, chatId, isCurrent, setMessages]);

  const handleFeedback = useCallback(
    (messageId: string, next: "up" | "down" | null) => {
      if (!token || !chatId) return;
      void api.setMessageFeedback(token, chatId, messageId, next).catch(() => undefined);
    },
    [token, chatId],
  );

  return { ...chat, loading, loadError, handleFeedback };
}
