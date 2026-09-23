import { useCallback, useSyncExternalStore } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { getSessionGeneration } from "@/lib/auth";

let pending: { session: number } | null = null;
const listeners = new Set<() => void>();
function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
function notify() { listeners.forEach((listener) => listener()); }

/** Keep one account's preference write exclusive even if its settings screen remounts. */
export function useMemoryToggle(isCurrentView: () => boolean, onError: () => void) {
  const { updateUser } = useAuth();
  const session = getSessionGeneration();
  const saving = useSyncExternalStore(subscribe, () => pending?.session === session);
  const toggle = useCallback((enabled: boolean) => {
    if (!isCurrentView() || session !== getSessionGeneration() || pending?.session === session) return;
    const request = { session };
    pending = request;
    notify();
    void updateUser({ memory_enabled: enabled })
      .catch(() => { if (isCurrentView() && session === getSessionGeneration()) onError(); })
      .finally(() => {
        if (pending === request) { pending = null; notify(); }
      });
  }, [isCurrentView, session, updateUser, onError]);
  return { saving, toggle };
}
