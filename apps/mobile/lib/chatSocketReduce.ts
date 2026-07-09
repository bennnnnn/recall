import type { Message, SearchSource } from "@/lib/api";
import { parseSearchSources, parseSearchSourcesJson, stripSearchSourcesFromContent } from "@/lib/searchSources";

export type ChatWsPayload = {
  type: string;
  content?: string;
  message?: string;
  message_id?: string;
  code?: string;
  phase?: string;
  reasoning?: string;
  final_content?: string;
  recalled?: string;
  memory_hints?: string;
  context_summarized?: string;
  todos_sync?: string;
  search_sources?: string;
  resolved_model?: string;
  requested_model?: string;
  fallback_used?: string;
};

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

export function parseMemoryHints(raw: string | undefined): string[] | undefined {
  if (!raw) return undefined;
  try {
    return JSON.parse(raw) as string[];
  } catch {
    return undefined;
  }
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
  recalled?: number;
  memory_hints?: string[];
  context_summarized?: number;
  search_sources?: SearchSource[];
  draftSearchSources?: SearchSource[];
  model?: string | null;
  fallback_used?: boolean;
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
    recalled,
    memory_hints,
    context_summarized,
    search_sources,
    draftSearchSources,
    model,
    fallback_used,
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
            recalled,
            memory_hints,
            context_summarized,
            search_sources:
              search_sources ??
              draftSearchSources ??
              parseSearchSources(finalContent ?? draftContent ?? m.content),
            model: model ?? m.model,
            fallback_used: fallback_used || m.fallback_used,
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
            recalled,
            memory_hints,
            context_summarized,
            search_sources:
              search_sources ??
              draftSearchSources ??
              parseSearchSources(finalContent ?? draftContent ?? m.content),
            model: model ?? m.model,
            fallback_used: fallback_used || m.fallback_used,
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
      fallback_used: fallback_used || undefined,
      recalled,
      memory_hints,
      context_summarized,
      search_sources: search_sources ?? parseSearchSources(content),
      created_at: new Date().toISOString(),
    },
  ];
}

/** Apply resolved model to the in-flight streaming bubble as soon as stream_end arrives. */
export function applyStreamEndModel(
  messages: Message[],
  model: string | undefined,
  fallbackUsed = false,
): Message[] {
  if (!model) return messages;
  return messages.map((m) =>
    m.id === "streaming" ? { ...m, model, fallback_used: fallbackUsed || undefined } : m,
  );
}

export function buildDoneMergeInput(
  payload: ChatWsPayload,
  draft: { content: string; search_sources?: SearchSource[] } | null,
  now = Date.now(),
  stoppedStreamedId: string | null = null,
): DoneMergeInput {
  const finalContent =
    typeof payload.final_content === "string" ? payload.final_content : undefined;
  return {
    finalId: payload.message_id ?? `streamed-${now}`,
    messageId: payload.message_id,
    draftContent: draft?.content ?? "",
    finalContent,
    recalled: payload.recalled ? Number(payload.recalled) : undefined,
    context_summarized: payload.context_summarized
      ? Number(payload.context_summarized)
      : undefined,
    memory_hints: parseMemoryHints(payload.memory_hints),
    search_sources: parsePayloadSearchSources(payload.search_sources),
    draftSearchSources: draft?.search_sources,
    model: payload.resolved_model ?? null,
    fallback_used: payload.fallback_used === "1" || payload.fallback_used === "true",
    stoppedStreamedId,
  };
}
