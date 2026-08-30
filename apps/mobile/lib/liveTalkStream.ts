import { notifyUnauthorized, requestSse } from "@/lib/api/client";
import {
  parseLiveTalkSseChunk,
  type LiveTalkSpeakEvent,
} from "@/lib/liveTalkEvents";

export type { LiveTalkSpeakEvent } from "@/lib/liveTalkEvents";
export {
  applyLiveTalkChatEvent,
  liveTalkLocalIds,
  parseLiveTalkSseChunk,
  parseLiveTalkSpeakEvent,
} from "@/lib/liveTalkEvents";

const LIVE_TALK_SSE_TIMEOUT_MS = 90_000;

export async function streamLiveTalkSpeak(options: {
  token: string;
  audioBase64: string;
  filename: string;
  chatId?: string | null;
  signal?: AbortSignal;
  onEvent: (event: LiveTalkSpeakEvent) => void;
}): Promise<void> {
  const response = await requestSse(
    "/speech/live/speak",
    options.token,
    {
      audio_base64: options.audioBase64,
      filename: options.filename,
      ...(options.chatId ? { chat_id: options.chatId } : {}),
    },
    options.signal,
    true,
    LIVE_TALK_SSE_TIMEOUT_MS,
  );

  if (!response.ok) {
    if (response.status === 401) notifyUnauthorized();
    const text = await response.text();
    throw Object.assign(new Error(text || `Live talk failed: ${response.status}`), {
      status: response.status,
    });
  }
  if (!response.body) {
    throw new Error("Live talk response has no body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseLiveTalkSseChunk(buffer);
    buffer = parsed.rest;
    for (const event of parsed.events) {
      if (event.type === "error") {
        throw Object.assign(new Error(event.detail || "Could not complete live talk"), {
          status: 502,
        });
      }
      options.onEvent(event);
    }
  }
  if (buffer.trim()) {
    const parsed = parseLiveTalkSseChunk(`${buffer}\n\n`);
    for (const event of parsed.events) {
      if (event.type === "error") {
        throw Object.assign(new Error(event.detail || "Could not complete live talk"), {
          status: 502,
        });
      }
      options.onEvent(event);
    }
  }
}
