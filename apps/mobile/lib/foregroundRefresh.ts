import { useEffect, useRef } from "react";
import { AppState, type AppStateStatus } from "react-native";

import { CONTEXT_REFRESH_STALE_MS } from "@/lib/cache/contextRefresh";

/**
 * What the app reads again when it comes back to the foreground, and how old each
 * may be before it is. Six AppState listeners each kept a rule of their own, and a
 * return after a few minutes sent six to nine requests (code-health audit NET-16):
 * the rules are this one table, and the listeners share one native subscription.
 */
export const FOREGROUND_STALE_MS = {
  /** The open chat's newest messages (a turn left running reloads at once). */
  chatMessages: CONTEXT_REFRESH_STALE_MS,
  todos: CONTEXT_REFRESH_STALE_MS,
  usage: CONTEXT_REFRESH_STALE_MS,
  models: 5 * 60_000,
  /** The device's push token at the server. */
  pushRegistration: 12 * 60 * 60_000,
  /** The connection check runs on every return: it clears a stale "No internet". */
  connectivity: 0,
} as const;

type Listener = (state: AppStateStatus) => void;

const listeners = new Set<Listener>();
let subscription: { remove: () => void } | null = null;

function dispatch(state: AppStateStatus): void {
  for (const listener of [...listeners]) listener(state);
}

/** Every AppState change, through the one native subscription. */
export function onAppStateChange(listener: Listener): () => void {
  listeners.add(listener);
  subscription ??= AppState.addEventListener("change", dispatch);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      subscription?.remove();
      subscription = null;
    }
  };
}

/** `refresh` (the latest one) each time the app comes back to the foreground. */
export function useOnForeground(refresh: () => void, enabled = true): void {
  const latest = useRef(refresh);
  latest.current = refresh;
  useEffect(() => {
    if (!enabled) return;
    return onAppStateChange((state) => {
      if (state === "active") latest.current();
    });
  }, [enabled]);
}
