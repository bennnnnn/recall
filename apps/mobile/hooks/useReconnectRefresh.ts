import { useCallback } from "react";
import { useFocusEffect } from "expo-router";

import { useLatestRef } from "@/lib/latestRef";
import { onReconnect } from "@/lib/reconnectRefresh";

/**
 * Reads this screen's list again once the API answers after an outage (lib/reconnectRefresh.ts):
 * `refresh` (the latest) runs once, a random 0–10 s later, while the screen has focus and
 * `onScreen` (the latest), when given, says its list is the one showing.
 */
export function useReconnectRefresh(refresh: () => void, onScreen?: () => boolean): void {
  const latest = useLatestRef({ refresh, onScreen });
  useFocusEffect(
    useCallback(
      () => onReconnect(() => latest.current.refresh(), () => latest.current.onScreen?.() ?? true),
      [latest],
    ),
  );
}
