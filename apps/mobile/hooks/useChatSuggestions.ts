import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, type Suggestion } from "@/lib/api";
import { consumeCreatedSuggestionSkip } from "@/lib/cache/chatListCache";
import {
  chatSuggestionLoadAction,
  shouldFetchChatSuggestions,
} from "@/lib/chatTurnRefresh";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

type Options = {
  token: string | null;
  chatId?: string | null;
  hasMessages?: boolean;
  /** Streaming, or an optimistic user bubble before the socket is open. */
  turnBusy?: boolean;
  refreshKey?: number | string | boolean;
};

export function useChatSuggestions({
  token,
  chatId = null,
  hasMessages = true,
  turnBusy = false,
  refreshKey,
}: Options) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const prevRefreshKeyRef = useRef(refreshKey);
  const prevHasMessagesRef = useRef(hasMessages);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const items = await api.listSuggestions(token);
      setSuggestions(items.slice(0, 3));
    } catch {
      /* keep prior chips on transient failure */
    }
  }, [token]);

  useEffect(() => {
    if (!token || !hasMessages) setSuggestions([]);
  }, [token, hasMessages]);

  useEffect(() => {
    const refreshKeyChanged = prevRefreshKeyRef.current !== refreshKey;
    const openedIdleThread = hasMessages && !prevHasMessagesRef.current && !turnBusy;
    prevRefreshKeyRef.current = refreshKey;
    prevHasMessagesRef.current = hasMessages;

    const action = chatSuggestionLoadAction({
      hasToken: Boolean(token),
      hasMessages,
      turnBusy,
    });
    if (
      !shouldFetchChatSuggestions({
        action,
        refreshKeyChanged,
        openedIdleThread,
      })
    ) {
      return;
    }
    if (chatId && consumeCreatedSuggestionSkip(chatId)) return;
    void load();
  }, [token, chatId, hasMessages, turnBusy, refreshKey, load]);

  const dismiss = useCallback(
    async (id: string) => {
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      if (!token) return;
      try {
        await api.dismissSuggestion(token, id);
      } catch {
        reportRecoverableError(feedback, t("reminders.dismiss_failed"));
        void load();
      }
    },
    [token, load, feedback, t],
  );

  return { suggestions, dismiss, refresh: load };
}
