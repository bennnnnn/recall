import { AppState, type AppStateStatus } from "react-native";

import { api } from "@/lib/api";

let lastForegroundSyncAt = 0;
const LOCAL_DEBOUNCE_MS = 60_000;

/** Sync Gmail on app open / foreground if the server throttle allows it. */
export async function maybeSyncGmailOnForeground(token: string): Promise<void> {
  const now = Date.now();
  if (now - lastForegroundSyncAt < LOCAL_DEBOUNCE_MS) return;
  lastForegroundSyncAt = now;

  try {
    const status = await api.googleGmailStatus(token);
    if (!status.connected) return;
    await api.syncGoogleGmail(token);
  } catch {
    /* best-effort */
  }
}

export function attachGmailForegroundSync(token: string | null): () => void {
  if (!token) return () => {};

  void maybeSyncGmailOnForeground(token);

  const onChange = (state: AppStateStatus) => {
    if (state === "active") {
      void maybeSyncGmailOnForeground(token);
    }
  };

  const sub = AppState.addEventListener("change", onChange);
  return () => sub.remove();
}
