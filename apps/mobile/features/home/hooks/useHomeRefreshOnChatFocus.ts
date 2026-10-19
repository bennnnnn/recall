import { useCallback } from "react";
import { useFocusEffect } from "expo-router";

import { useHome } from "@/features/home/context/HomeContext";
import { shouldRefreshHomeOnChatFocus } from "@/lib/cache/contextRefresh";

/**
 * The chat screen shows Home (greeting, one overdue reminder) while no thread
 * is open; coming back to it refreshes Home quietly when it was never fetched.
 */
export function useHomeRefreshOnChatFocus(routeChatId: string | undefined, chatId: string | null) {
  const { refresh: refreshHome, hasFetched: hasFetchedHome } = useHome();
  useFocusEffect(
    useCallback(() => {
      const openThread =
        (typeof routeChatId === "string" && routeChatId) || chatId;
      if (
        !shouldRefreshHomeOnChatFocus({
          hasOpenThread: Boolean(openThread),
          hasFetchedHome,
        })
      ) {
        return;
      }
      void refreshHome({ silent: true });
    }, [refreshHome, routeChatId, chatId, hasFetchedHome]),
  );
}
