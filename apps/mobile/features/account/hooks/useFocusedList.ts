import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";

/**
 * A list a Settings page reads again each time it gains focus (archived chats,
 * signed-in devices). A failed read sets `loadError` and keeps the rows it had:
 * it must never look like an empty list. `read` must keep its identity.
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

  return { items, setItems, loading, loadError, load };
}
