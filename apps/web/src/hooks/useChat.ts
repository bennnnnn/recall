import { useCallback, useEffect, useRef, useState } from "react";
import { chatsApi } from "@/api/chats";
import { streamMessage, streamRegenerate } from "@/api/stream";
import type { Message } from "@/api/types";

const STREAMING_ID = "streaming";

export function useChat(token: string, chatId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [statusPhase, setStatusPhase] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Load messages when the chat changes.
  useEffect(() => {
    if (!chatId || !token) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    chatsApi
      .listMessages(token, chatId, { limit: 100 })
      .then((page) => {
        if (!cancelled) setMessages(page.messages);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load chat");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, chatId]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
    setStatusPhase(null);
  }, []);

  const send = useCallback(
    async (content: string, model = "auto") => {
      if (!chatId || !token || !content.trim() || streaming) return;
      setError(null);
      setStatusPhase(null);
      const userMessage: Message = {
        id: `local-${Date.now()}`,
        role: "user",
        content,
        model: null,
        created_at: new Date().toISOString(),
      };
      const assistantPlaceholder: Message = {
        id: STREAMING_ID,
        role: "assistant",
        content: "",
        model: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await streamMessage(
          token,
          chatId,
          { content, model, client_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
          {
            onEvent: (event) => {
              switch (event.type) {
                case "start":
                  break;
                case "status":
                  setStatusPhase(event.detail ?? event.phase);
                  break;
                case "reasoning":
                  // Slice 1: reasoning is not surfaced in the bubble. Could
                  // render as a collapsible "thinking" block in a later slice.
                  break;
                case "token":
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === STREAMING_ID
                        ? { ...m, content: m.content + event.content }
                        : m,
                    ),
                  );
                  break;
                case "stream_end":
                  setStatusPhase(null);
                  break;
                case "done":
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === STREAMING_ID
                        ? {
                            ...m,
                            id: event.message_id ?? `msg-${Date.now()}`,
                            // final_content is the post-stream-corrected text
                            // (e.g. validate_math_fences). Prefer it over the
                            // streamed draft so the bubble matches the DB.
                            content:
                              event.final_content ??
                              prev.find((x) => x.id === STREAMING_ID)?.content ??
                              "",
                            model: event.resolved_model ?? null,
                          }
                        : m,
                    ),
                  );
                  break;
                case "error":
                  setError(event.message);
                  setMessages((prev) =>
                    prev.filter((m) => m.id !== STREAMING_ID),
                  );
                  break;
              }
            },
            onError: (e) => setError(e.message),
          },
          controller.signal,
        );
      } catch (e) {
        if (!controller.signal.aborted) {
          setError(e instanceof Error ? e.message : "Stream failed");
        }
      } finally {
        setStreaming(false);
        setStatusPhase(null);
        abortRef.current = null;
      }
    },
    [token, chatId, streaming],
  );

  const regenerate = useCallback(
    async (model = "auto") => {
      if (!chatId || !token || streaming) return;
      setError(null);
      setStatusPhase(null);
      // Drop the last assistant turn; the regenerate stream replaces it.
      setMessages((prev) => {
        const next = [...prev];
        // Remove trailing assistant message(s) back to the last user turn.
        while (next.length > 0 && next[next.length - 1].role === "assistant") {
          next.pop();
        }
        next.push({
          id: STREAMING_ID,
          role: "assistant",
          content: "",
          model: null,
          created_at: new Date().toISOString(),
        });
        return next;
      });
      setStreaming(true);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await streamRegenerate(
          token,
          chatId,
          { model, client_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
          {
            onEvent: (event) => {
              switch (event.type) {
                case "status":
                  setStatusPhase(event.detail ?? event.phase);
                  break;
                case "token":
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === STREAMING_ID
                        ? { ...m, content: m.content + event.content }
                        : m,
                    ),
                  );
                  break;
                case "stream_end":
                  setStatusPhase(null);
                  break;
                case "done":
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === STREAMING_ID
                        ? {
                            ...m,
                            id: event.message_id ?? `msg-${Date.now()}`,
                            content:
                              event.final_content ??
                              prev.find((x) => x.id === STREAMING_ID)?.content ??
                              "",
                            model: event.resolved_model ?? null,
                          }
                        : m,
                    ),
                  );
                  break;
                case "error":
                  setError(event.message);
                  setMessages((prev) =>
                    prev.filter((m) => m.id !== STREAMING_ID),
                  );
                  break;
              }
            },
            onError: (e) => setError(e.message),
          },
          controller.signal,
        );
      } catch (e) {
        if (!controller.signal.aborted) {
          setError(e instanceof Error ? e.message : "Regenerate failed");
        }
      } finally {
        setStreaming(false);
        setStatusPhase(null);
        abortRef.current = null;
      }
    },
    [token, chatId, streaming],
  );

  return {
    messages,
    loading,
    streaming,
    statusPhase,
    error,
    send,
    stop,
    regenerate,
  };
}
