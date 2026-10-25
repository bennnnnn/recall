import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";

import { useReconnectRefresh } from "@/hooks/useReconnectRefresh";

/**
 * A list a Settings page reads again each time it gains focus (archived chats,
 * signed-in devices), and once more when the API answers after an outage, while it
 * has focus (hooks/useReconnectRefresh.ts). A failed read sets `loadError` and keeps
 * the rows it had: it must never look like an empty list. `read` must keep its identity.
 */
export function useFocusedList<T>(token: string | null, read: (token: string) => Promise<T[]>) {
  const [items, setItems] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setLoadError(false);
    try {
      setItems(await read(token));
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [token, read]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );
  useReconnectRefresh(() => void load());

  return { items, setItems, loading, loadError, load };
}
