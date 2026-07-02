import { getApiUrl } from "@/lib/config";
import type { ClientGeo } from "@/lib/clientGeo";
import { clientGeoWsFields } from "@/lib/clientGeo";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { parseChatWsPayload } from "@/lib/chatSocketReduce";

export type ChatSsePayload = NonNullable<ReturnType<typeof parseChatWsPayload>>;

type StreamChatMessageOptions = {
  token: string;
  chatId: string;
  content: string;
  attachmentIds?: string[];
  model?: string | null;
  clientGeo?: ClientGeo | null;
  signal?: AbortSignal;
  onEvent: (payload: ChatSsePayload) => void;
};

function parseSseChunk(buffer: string): { events: ChatSsePayload[]; rest: string } {
  const events: ChatSsePayload[] = [];
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const part of parts) {
    for (const line of part.split("\n")) {
      if (!line.startsWith("data: ")) continue;
      const payload = parseChatWsPayload(line.slice(6));
      if (payload) events.push(payload);
    }
  }
  return { events, rest };
}

export async function streamChatMessageSse(
  options: StreamChatMessageOptions,
): Promise<void> {
  const response = await fetch(
    `${getApiUrl()}/chats/${options.chatId}/messages/stream`,
    {
      method: "POST",
      signal: options.signal,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${options.token}`,
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        content: options.content,
        model: options.model ?? null,
        attachment_ids: options.attachmentIds ?? [],
        client_timezone: getDeviceTimezone(),
        ...clientGeoWsFields(options.clientGeo),
      }),
    },
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `SSE request failed: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("SSE response has no body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseChunk(buffer);
    buffer = parsed.rest;
    for (const event of parsed.events) {
      options.onEvent(event);
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseChunk(`${buffer}\n\n`);
    for (const event of parsed.events) {
      options.onEvent(event);
    }
  }
}
