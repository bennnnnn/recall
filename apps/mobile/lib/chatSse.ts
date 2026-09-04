import type { ClientGeo } from "@/lib/clientGeo";
import { clientGeoWsFields } from "@/lib/clientGeo";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { notifyUnauthorized, requestSse } from "@/lib/api/client";
import { parseChatWsPayload } from "@/lib/chatSocketReduce";

export type ChatSsePayload = NonNullable<ReturnType<typeof parseChatWsPayload>>;

export function isSseAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

/** Abort the previous SSE only when replacing a stream in the same chat.
 * New chat / leave must not abort — Stop is the only hard cancel (WS drains
 * on disconnect; SSE Stop is abort, so a chat switch must leave the fetch
 * running). */
export function shouldAbortPriorSse(
  previousChatId: string | null,
  nextChatId: string | null,
): boolean {
  return previousChatId != null && nextChatId != null && previousChatId === nextChatId;
}

type StreamChatSseClient = {
  token: string;
  chatId: string;
  model?: string | null;
  clientGeo?: ClientGeo | null;
  signal?: AbortSignal;
  onEvent: (payload: ChatSsePayload) => void;
};

type StreamChatMessageOptions = StreamChatSseClient & {
  content: string;
  attachmentIds?: string[];
};

async function streamChatSseRequest(
  path: string,
  options: StreamChatSseClient,
  extraBody: Record<string, unknown> = {},
): Promise<void> {
  // Route through lib/api's requestSse so this stream shares the REST path's
  // 401→refresh→retry behaviour and the lib/api boundary stays the single
  // network egress point (no bare fetch(getApiUrl()...) here).
  const body = {
    ...extraBody,
    model: options.model ?? null,
    client_timezone: getDeviceTimezone(),
    ...clientGeoWsFields(options.clientGeo),
  };
  const response = await requestSse(path, options.token, body, options.signal);

  if (!response.ok) {
    if (response.status === 401) {
      notifyUnauthorized();
    }
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

export function parseSseChunk(buffer: string): { events: ChatSsePayload[]; rest: string } {
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
  await streamChatSseRequest(`/chats/${options.chatId}/messages/stream`, options, {
    content: options.content,
    attachment_ids: options.attachmentIds ?? [],
  });
}

export async function streamChatRegenerateSse(
  options: StreamChatSseClient,
): Promise<void> {
  await streamChatSseRequest(`/chats/${options.chatId}/regenerate/stream`, options);
}
