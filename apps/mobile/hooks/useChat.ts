import { useCallback, useEffect, useRef, useState } from "react";
import { chatWebSocketUrl, Message, SearchSource } from "@/lib/api";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { isVocabQuizAnswer } from "@/lib/parseVocabQuiz";
import { parseSearchSources, parseSearchSourcesJson } from "@/lib/searchSources";

const CONNECT_TIMEOUT_MS = 8000;

export type StreamingDraft = {
  content: string;
  search_sources?: SearchSource[];
};

type UseChatOptions = {
  /** Called with the new title when the server sends one after first reply */
  onFirstReply?: () => void;
  /** Called when the server or socket reports an error */
  onError?: (message: string, code?: string) => void;
  /** Refresh lists/reminders after chat may have synced todos */
  onTodosSync?: () => void;
};

export function useChat(
  token: string | null,
  chatId: string | null,
  options: UseChatOptions = {},
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [streamingDraft, setStreamingDraft] = useState<StreamingDraft | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const connectingRef = useRef<Promise<void> | null>(null);
  const assistantBuffer = useRef("");
  const streamingDraftRef = useRef<StreamingDraft | null>(null);
  const streamingRef = useRef(false);

  const updateStreamingDraft = useCallback((draft: StreamingDraft | null) => {
    streamingDraftRef.current = draft;
    setStreamingDraft(draft);
  }, []);
  const firstReplyRef = useRef(false);
  const onFirstReplyRef = useRef(options.onFirstReply);
  const onErrorRef = useRef(options.onError);
  const onTodosSyncRef = useRef(options.onTodosSync);
  onFirstReplyRef.current = options.onFirstReply;
  onErrorRef.current = options.onError;
  onTodosSyncRef.current = options.onTodosSync;

  const reportError = useCallback((message: string, code?: string) => {
    onErrorRef.current?.(message, code);
  }, []);

  const clearStreamingBubble = useCallback(() => {
    updateStreamingDraft(null);
    setMessages((prev) => prev.filter((m) => m.id !== "streaming"));
  }, [updateStreamingDraft]);

  const appendStreamingPlaceholder = useCallback(() => {
    setMessages((prev) => {
      if (prev.some((m) => m.id === "streaming")) return prev;
      return [
        ...prev,
        {
          id: "streaming",
          role: "assistant" as const,
          content: "",
          model: null,
          created_at: new Date().toISOString(),
        },
      ];
    });
  }, []);

  // Keep streamingRef in sync so onclose/onerror closures always see fresh value
  useEffect(() => {
    streamingRef.current = streaming;
  }, [streaming]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  // Close and reset socket when chat changes
  useEffect(() => {
    wsRef.current?.close();
    wsRef.current = null;
    connectingRef.current = null;
    assistantBuffer.current = "";
    firstReplyRef.current = false;
    updateStreamingDraft(null);
    setStreaming(false);
  }, [chatId, updateStreamingDraft]);

  const connect = useCallback((): Promise<void> => {
    if (!token || !chatId) return Promise.resolve();
    if (wsRef.current?.readyState === WebSocket.OPEN) return Promise.resolve();
    // Reuse an in-flight connection so concurrent callers don't tear each other down
    if (connectingRef.current) return connectingRef.current;

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const connectPromise = new Promise<void>((resolve, reject) => {
      const ws = new WebSocket(chatWebSocketUrl(chatId));
      wsRef.current = ws;

      const timer = setTimeout(() => {
        ws.close();
        reject(new Error("WebSocket connection timed out"));
      }, CONNECT_TIMEOUT_MS);

      ws.onopen = () => {
        clearTimeout(timer);
        ws.send(
          JSON.stringify({
            token,
            client_timezone: getDeviceTimezone(),
          }),
        );
        resolve();
      };

      ws.onerror = () => {
        clearTimeout(timer);
        setStreaming(false);
        streamingRef.current = false;
        reject(new Error("WebSocket error"));
      };

      ws.onclose = () => {
        clearTimeout(timer);
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        if (streamingRef.current) {
          setStreaming(false);
          streamingRef.current = false;
          const hadContent = assistantBuffer.current.trim().length > 0;
          const draft = streamingDraftRef.current;
          assistantBuffer.current = "";
          updateStreamingDraft(null);
          setMessages((prev) => {
            const streamingMsg = prev.find((m) => m.id === "streaming");
            if (!streamingMsg) return prev;
            if (!hadContent) {
              return prev.filter((m) => m.id !== "streaming");
            }
            return prev.map((m) =>
              m.id === "streaming"
                ? {
                    ...m,
                    id: `streamed-${Date.now()}`,
                    content: draft?.content ?? m.content,
                    search_sources: draft?.search_sources ?? m.search_sources,
                  }
                : m,
            );
          });
          if (!hadContent) {
            reportError("Connection lost before the reply arrived. Try again.");
          }
        }
      };

      ws.onmessage = (event) => {
        let payload: {
          type: string;
          content?: string;
          message?: string;
          message_id?: string;
          code?: string;
          recalled?: string;
          memory_hints?: string;
          context_summarized?: string;
          todos_sync?: string;
          search_sources?: string;
        };
        try {
          payload = JSON.parse(event.data);
        } catch {
          return;
        }

        if (payload.type === "start") {
          setStreaming(true);
          streamingRef.current = true;
          assistantBuffer.current = "";
          updateStreamingDraft({ content: "" });
          appendStreamingPlaceholder();
        }

        if (payload.type === "token") {
          assistantBuffer.current += payload.content ?? "";
          const streamedSources = parseSearchSources(assistantBuffer.current);
          updateStreamingDraft({
            content: assistantBuffer.current,
            search_sources: streamedSources.length ? streamedSources : undefined,
          });
        }

        if (payload.type === "stream_end") {
          setStreaming(false);
          streamingRef.current = false;
        }

        if (payload.type === "done") {
          setStreaming(false);
          streamingRef.current = false;
          assistantBuffer.current = "";
          const finalId = payload.message_id ?? `streamed-${Date.now()}`;
          const recalled = payload.recalled
            ? Number(payload.recalled)
            : undefined;
          const context_summarized = payload.context_summarized
            ? Number(payload.context_summarized)
            : undefined;
          let memory_hints: string[] | undefined;
          if (payload.memory_hints) {
            try {
              memory_hints = JSON.parse(payload.memory_hints) as string[];
            } catch {
              memory_hints = undefined;
            }
          }
          let search_sources: SearchSource[] | undefined;
          if (payload.search_sources) {
            const parsed = parseSearchSourcesJson(payload.search_sources);
            if (parsed.length > 0) search_sources = parsed;
          }
          // Authoritative persisted text from the server (only sent on a
          // user-initiated stop). Reconciles the local `streamed-*` bubble,
          // which may be shorter than what the DB persisted.
          const finalContent =
            typeof payload.final_content === "string" ? payload.final_content : undefined;
          const draft = streamingDraftRef.current;
          updateStreamingDraft(null);
          setMessages((prev) => {
            if (prev.some((m) => m.id === "streaming")) {
              const draftContent = draft?.content ?? "";
              if (!payload.message_id && !draftContent.trim()) {
                return prev.filter((m) => m.id !== "streaming");
              }
              return prev.map((m) =>
                m.id === "streaming"
                  ? {
                      ...m,
                      id: finalId,
                      content: draftContent || m.content,
                      recalled,
                      memory_hints,
                      context_summarized,
                      search_sources: search_sources ?? draft?.search_sources,
                    }
                  : m,
              );
            }
            const next = [...prev];
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].role === "assistant") {
                next[i] = {
                  ...next[i],
                  id: finalId,
                  // Prefer the server's final persisted content (stop case) over
                  // the locally-frozen draft, which can be shorter than the DB.
                  content: finalContent ?? next[i].content,
                  recalled,
                  memory_hints,
                  context_summarized,
                  search_sources,
                };
                break;
              }
            }
            return next;
          });
          if (!firstReplyRef.current) {
            firstReplyRef.current = true;
            onFirstReplyRef.current?.();
          }
          if (payload.todos_sync === "1") {
            onTodosSyncRef.current?.();
            setTimeout(() => onTodosSyncRef.current?.(), 2500);
          }
        }

        if (payload.type === "error") {
          setStreaming(false);
          streamingRef.current = false;
          assistantBuffer.current = "";
          clearStreamingBubble();
          reportError(
            payload.message ?? "Something went wrong. Try again.",
            typeof payload.code === "string" ? payload.code : undefined,
          );
        }
      };
    });

    connectingRef.current = connectPromise;
    connectPromise.then(
      () => {
        connectingRef.current = null;
      },
      () => {
        connectingRef.current = null;
      },
    );
    return connectPromise;
  }, [
    token,
    chatId,
    appendStreamingPlaceholder,
    clearStreamingBubble,
    reportError,
    updateStreamingDraft,
  ]);

  const ensureConnected = useCallback(async () => {
    try {
      await connect();
    } catch {
      reportError(
        "Could not connect to the server. Check your network and API URL.",
      );
    }
  }, [connect, reportError]);

  const sendMessage = useCallback(
    async (
      content: string,
      options?: {
        skipUserBubble?: boolean;
        attachmentIds?: string[];
        localImageUri?: string | null;
        model?: string | null;
      },
    ) => {
      if (!token || !chatId) return;

      if (!options?.skipUserBubble) {
        setMessages((prev) => [
          ...prev,
          {
            id: `local-${Date.now()}`,
            role: "user",
            content,
            model: null,
            local_image_uri: options?.localImageUri ?? null,
            created_at: new Date().toISOString(),
          },
        ]);
      }

      await ensureConnected();
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;

      assistantBuffer.current = "";
      if (isVocabQuizAnswer(content) && !streamingRef.current) {
        setStreaming(true);
        streamingRef.current = true;
        updateStreamingDraft({ content: "" });
        appendStreamingPlaceholder();
      }
      wsRef.current.send(
        JSON.stringify({
          type: "message",
          content,
          attachment_ids: options?.attachmentIds ?? [],
          model: options?.model ?? null,
        }),
      );
    },
    [token, chatId, ensureConnected, appendStreamingPlaceholder, updateStreamingDraft],
  );

  const regenerateResponse = useCallback(
    async (model?: string | null) => {
      if (!token || !chatId) return;

      setMessages((prev) => {
        const next = [...prev];
        if (next[next.length - 1]?.role === "assistant") next.pop();
        return next;
      });

      await ensureConnected();
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;

      assistantBuffer.current = "";
      wsRef.current.send(
        JSON.stringify({ type: "regenerate", model: model ?? null }),
      );
    },
    [token, chatId, ensureConnected],
  );

  const editMessage = useCallback(
    async (messageId: string, content: string, model?: string | null) => {
      if (!token || !chatId || !content.trim()) return;

      setMessages((prev) => {
        const index = prev.findIndex((m) => m.id === messageId);
        if (index < 0) return prev;
        return [
          ...prev.slice(0, index),
          {
            id: `local-edit-${Date.now()}`,
            role: "user" as const,
            content: content.trim(),
            model: null,
            created_at: new Date().toISOString(),
          },
        ];
      });

      await ensureConnected();
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;

      assistantBuffer.current = "";
      wsRef.current.send(
        JSON.stringify({
          type: "edit",
          message_id: messageId,
          content: content.trim(),
          model: model ?? null,
        }),
      );
    },
    [token, chatId, ensureConnected],
  );

  const stopGeneration = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "cancel" }));
    setStreaming(false);
    streamingRef.current = false;
    const draft = streamingDraftRef.current;
    assistantBuffer.current = "";
    updateStreamingDraft(null);
    setMessages((prev) => {
      const streamingMsg = prev.find((m) => m.id === "streaming");
      if (!streamingMsg) return prev;
      const content = draft?.content ?? streamingMsg.content;
      if (!content.trim()) {
        return prev.filter((m) => m.id !== "streaming");
      }
      return prev.map((m) =>
        m.id === "streaming"
          ? {
              ...m,
              id: `streamed-${Date.now()}`,
              content,
              search_sources: draft?.search_sources ?? m.search_sources,
            }
          : m,
      );
    });
  }, [updateStreamingDraft]);

  return {
    messages,
    setMessages,
    streaming,
    streamingDraft,
    sendMessage,
    regenerateResponse,
    editMessage,
    stopGeneration,
    connect,
  };
}
