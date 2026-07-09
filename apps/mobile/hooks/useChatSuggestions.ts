import { useCallback, useEffect, useState } from "react";
import { Alert } from "react-native";
import { useTranslation } from "react-i18next";

import { api, type Suggestion } from "@/lib/api";

type Options = {
  token: string | null;
  enabled?: boolean;
  refreshKey?: number | string | boolean;
};

export function useChatSuggestions({ token, enabled = true, refreshKey }: Options) {
  const { t } = useTranslation();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  const refresh = useCallback(async () => {
    if (!token || !enabled) {
      setSuggestions([]);
      return;
    }
    try {
      const items = await api.listSuggestions(token);
      setSuggestions(items.slice(0, 3));
    } catch {
      /* keep prior chips on transient failure */
    }
  }, [token, enabled]);

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
