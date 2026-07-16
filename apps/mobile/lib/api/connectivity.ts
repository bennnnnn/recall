import { getApiUrl } from "@/lib/config";

import { apiUrl } from "@/lib/api/client";

export function chatWebSocketUrl(chatId: string) {
  const base = getApiUrl().replace(/^http/, "ws");
  return `${base}/ws/chats/${chatId}`;
}

export async function checkHealth(timeoutMs = 4000): Promise<boolean> {
  // AbortController + timeout so a hung network (e.g. a captive portal that
  // holds the connection open without responding) doesn't pile up overlapping
  // fetches when this is polled while the offline banner is visible. The timer
  // is cleared in `finally` so a rejected/aborted fetch never leaks it.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(apiUrl("/health"), { signal: controller.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}
