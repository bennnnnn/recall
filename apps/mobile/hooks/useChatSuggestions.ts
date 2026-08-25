import { useCallback, useEffect, useState } from "react";
import { Alert } from "react-native";
import { useTranslation } from "react-i18next";

import { api, type Suggestion } from "@/lib/api";
import { chatSuggestionLoadAction } from "@/lib/chatTurnRefresh";

type Options = {
  token: string | null;
  hasMessages?: boolean;
  streamActive?: boolean;
  refreshKey?: number | string | boolean;
};

export function useChatSuggestions({
  token,
  hasMessages = true,
  streamActive = false,
  refreshKey,
}: Options) {
  const { t } = useTranslation();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  const refresh = useCallback(async () => {
    const next = chatSuggestionLoadAction({
      hasToken: Boolean(token),
      hasMessages,
      streamActive,
    });
    if (next === "clear") {
      setSuggestions([]);
      return;
    }
    if (next === "hold" || !token) return;
    try {
      const items = await api.listSuggestions(token);
      setSuggestions(items.slice(0, 3));
    } catch {
      /* keep prior chips on transient failure */
    }
  }, [token, hasMessages, streamActive]);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshKey]);

  const dismiss = useCallback(
    async (id: string) => {
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
      if (!token) return;
      try {
        await api.dismissSuggestion(token, id);
      } catch {
        Alert.alert(t("common.error"), t("reminders.dismiss_failed"));
        void refresh();
      }
    },
    [token, refresh, t],
  );

  return { suggestions, dismiss, refresh };
}
