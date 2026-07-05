import { getApiUrl } from "@/lib/config";

import { apiUrl } from "@/lib/api/client";

export function chatWebSocketUrl(chatId: string) {
  const base = getApiUrl().replace(/^http/, "ws");
  return `${base}/ws/chats/${chatId}`;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(apiUrl("/health"));
    return res.ok;
  } catch {
    return false;
  }
}
