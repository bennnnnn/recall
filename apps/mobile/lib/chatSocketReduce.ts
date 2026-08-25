import type { Message, SearchSource } from "@/lib/api";
import { parseSearchSources, parseSearchSourcesJson, stripSearchSourcesFromContent } from "@/lib/searchSources";

export type ChatWsPayload = {
  type: string;
  content?: string;
  message?: string;
  message_id?: string;
  code?: string;
  phase?: string;
  /** Optional activity context for a `status` event (e.g. the search query). */
  detail?: string;
  reasoning?: string;
  final_content?: string;
  todos_sync?: string;
  search_sources?: string;
  resolved_model?: string;
};

const STOPPED_STREAM_DELTA_TYPES = new Set([
  "token",
  "status",
  "reasoning",
  "stream_end",
]);

/** Late stream deltas after Stop must not mutate the committed partial bubble. */
export function shouldIgnoreStoppedStreamEvent(
  type: string,
  streaming: boolean,
): boolean {
  return !streaming && STOPPED_STREAM_DELTA_TYPES.has(type);
}

export function parseChatWsPayload(raw: string): ChatWsPayload | null {
  try {
    return JSON.parse(raw) as ChatWsPayload;
  } catch {
    return null;
  }
}

export function appendToken(buffer: string, token: string | undefined): string {
  return buffer + (token ?? "");
}

export function parsePayloadSearchSources(
  raw: string | undefined,
): SearchSource[] | undefined {
  if (!raw) return undefined;
  const parsed = parseSearchSourcesJson(raw);
  return parsed.length > 0 ? parsed : undefined;
}

export type DoneMergeInput = {
  finalId: string;
  messageId?: string;
  draftContent: string;
  finalContent?: string;
  search_sources?: SearchSource[];
  draftSearchSources?: SearchSource[];
  reasoning_preview?: string;
  model?: string | null;
  /**
   * Local id given to the streaming bubble when the user stopped generation
   * (e.g. `streamed-<ts>`). When the server's `done` arrives after a stop,
   * we reconcile that bubble in place (picking up the authoritative
   * `final_content` + real `message_id`) instead of appending a duplicate.
   * If non-null and the id is no longer present, the `done` is dropped.
   */
  stoppedStreamedId?: string | null;
};

/** Pure merge for the WebSocket `done` event — used by useChat and unit tests. */
export function mergeDoneIntoMessages(
  prev: Message[],
  input: DoneMergeInput,
): Message[] {
  const {
    finalId,
    messageId,
    draftContent,
    finalContent,
    search_sources,
    draftSearchSources,
    reasoning_preview,
    model,
    stoppedStreamedId,
  } = input;

  if (prev.some((m) => m.id === "streaming")) {
    if (!messageId && !draftContent.trim()) {
      return prev.filter((m) => m.id !== "streaming");
    }
    return prev.map((m) =>
      m.id === "streaming"
        ? {
            ...m,
            id: finalId,
            renderKey: m.renderKey,
            content: stripSearchSourcesFromContent(
              finalContent ?? (draftContent || m.content),
            ),
            search_sources:
              search_sources ??
              draftSearchSources ??
              parseSearchSources(finalContent ?? draftContent ?? m.content),
            reasoning_preview,
            model: model ?? m.model,
          }
        : m,
    );
  }

  // User stopped generation: the streaming bubble was already committed
  // locally as `stoppedStreamedId`. Reconcile it with the server's
  // authoritative done (real id + final_content) instead of appending.
  if (stoppedStreamedId) {
    if (!prev.some((m) => m.id === stoppedStreamedId)) {
      // Bubble is gone (chat switched / new send) — drop the late done.
      return prev;
    }
    const content = stripSearchSourcesFromContent(finalContent ?? draftContent);
    if (!messageId && !content.trim()) {
      return prev.filter((m) => m.id !== stoppedStreamedId);
    }
    return prev.map((m) =>
      m.id === stoppedStreamedId
        ? {
            ...m,
            id: finalId,
            content,
            search_sources:
              search_sources ??
              draftSearchSources ??
              parseSearchSources(finalContent ?? draftContent ?? m.content),
            reasoning_preview,
            model: model ?? m.model,
          }
        : m,
    );
  }

  const next = [...prev];
  const content = stripSearchSourcesFromContent(finalContent ?? draftContent);
  if (!content.trim()) {
    return next;
  }
  return [
    ...next,
    {
      id: finalId,
      role: "assistant" as const,
      content,
      model: model ?? null,
      search_sources: search_sources ?? parseSearchSources(content),
      created_at: new Date().toISOString(),
    },
  ];
}

/** Apply resolved model to the in-flight streaming bubble as soon as stream_end arrives. */
export function applyStreamEndModel(
  messages: Message[],
  model: string | undefined,
): Message[] {
  if (!model) return messages;
  return messages.map((m) =>
    m.id === "streaming" ? { ...m, model } : m,
  );
}

export function buildDoneMergeInput(
  payload: ChatWsPayload,
  draft: { content: string; search_sources?: SearchSource[]; reasoning?: string } | null,
  now = Date.now(),
  stoppedStreamedId: string | null = null,
): DoneMergeInput {
  const finalContent =
    typeof payload.final_content === "string" ? payload.final_content : undefined;
  const reasoningPreview = draft?.reasoning?.trim();
  return {
    finalId: payload.message_id ?? `streamed-${now}`,
    messageId: payload.message_id,
    draftContent: draft?.content ?? "",
    finalContent,
    search_sources: parsePayloadSearchSources(payload.search_sources),
    draftSearchSources: draft?.search_sources,
    reasoning_preview: reasoningPreview || undefined,
    model: payload.resolved_model ?? null,
    stoppedStreamedId,
  };
}
