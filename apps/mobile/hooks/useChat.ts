import { useCallback, useEffect, useRef, useState } from "react";

import { chatWebSocketUrl, Message } from "@/lib/api";

const CONNECT_TIMEOUT_MS = 8000;

type UseChatOptions = {
  /** Called with the new title when the server sends one after first reply */
  onFirstReply?: () => void;
  /** Called when the server or socket reports an error */
  onError?: (message: string) => void;
};

export function useChat(
  token: string | null,
  chatId: string | null,
  options: UseChatOptions = {},
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const connectingRef = useRef<Promise<void> | null>(null);
  const assistantBuffer = useRef("");
  const streamingRef = useRef(false);
  const firstReplyRef = useRef(false);
  const onFirstReplyRef = useRef(options.onFirstReply);
  const onErrorRef = useRef(options.onError);
  onFirstReplyRef.current = options.onFirstReply;
  onErrorRef.current = options.onError;

  const reportError = useCallback((message: string) => {
    onErrorRef.current?.(message);
  }, []);

  const clearStreamingBubble = useCallback(() => {
    setMessages((prev) => prev.filter((m) => m.id !== "streaming"));
  }, []);

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
    setStreaming(false);
  }, [chatId]);

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
        ws.send(JSON.stringify({ token }));
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
          assistantBuffer.current = "";
          setMessages((prev) => {
            const streamingMsg = prev.find((m) => m.id === "streaming");
            if (!streamingMsg) return prev;
            if (!hadContent) {
              return prev.filter((m) => m.id !== "streaming");
            }
            return prev.map((m) =>
              m.id === "streaming" ? { ...m, id: `streamed-${Date.now()}` } : m,
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
          recalled?: string;
          memory_hints?: string;
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
          appendStreamingPlaceholder();
        }

        if (payload.type === "token") {
          assistantBuffer.current += payload.content ?? "";
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant" && last.id === "streaming") {
              next[next.length - 1] = {
                ...last,
                content: assistantBuffer.current,
              };
            } else {
              next.push({
                id: "streaming",
                role: "assistant",
                content: assistantBuffer.current,
                model: null,
                created_at: new Date().toISOString(),
              });
            }
            return next;
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
          let memory_hints: string[] | undefined;
          if (payload.memory_hints) {
            try {
              memory_hints = JSON.parse(payload.memory_hints) as string[];
            } catch {
              memory_hints = undefined;
            }
          }
          setMessages((prev) => {
            if (prev.some((m) => m.id === "streaming")) {
              const streamingMsg = prev.find((m) => m.id === "streaming");
              if (!payload.message_id && !streamingMsg?.content.trim()) {
                return prev.filter((m) => m.id !== "streaming");
              }
              return prev.map((m) =>
                m.id === "streaming"
                  ? { ...m, id: finalId, recalled, memory_hints }
                  : m,
              );
            }
            const next = [...prev];
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].role === "assistant") {
                next[i] = { ...next[i], id: finalId, recalled, memory_hints };
                break;
              }
            }
            return next;
          });
          if (!firstReplyRef.current) {
            firstReplyRef.current = true;
            onFirstReplyRef.current?.();
          }
        }

        if (payload.type === "error") {
          setStreaming(false);
          streamingRef.current = false;
          assistantBuffer.current = "";
          clearStreamingBubble();
          reportError(payload.message ?? "Something went wrong. Try again.");
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
      model?: string,
      options?: { skipUserBubble?: boolean },
    ) => {
      if (!token || !chatId) return;

      if (!options?.skipUserBubble) {
        setMessages((prev) => [
          ...prev,
          {
            id: `local-${Date.now()}`,
            role: "user",
            content,
            model: model ?? null,
            created_at: new Date().toISOString(),
          },
        ]);
      }

      await ensureConnected();
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;

      assistantBuffer.current = "";
      wsRef.current.send(JSON.stringify({ type: "message", content, model }));
    },
    [token, chatId, ensureConnected],
  );

  const regenerateResponse = useCallback(
    async (model?: string) => {
      if (!token || !chatId) return;

      setMessages((prev) => {
        const next = [...prev];
        if (next[next.length - 1]?.role === "assistant") next.pop();
        return next;
      });

      await ensureConnected();
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;

      assistantBuffer.current = "";
      wsRef.current.send(JSON.stringify({ type: "regenerate", model }));
    },
    [token, chatId, ensureConnected],
  );

  const stopGeneration = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "cancel" }));
    setStreaming(false);
    streamingRef.current = false;
    assistantBuffer.current = "";
    setMessages((prev) => {
      const streamingMsg = prev.find((m) => m.id === "streaming");
      if (!streamingMsg) return prev;
      if (!streamingMsg.content.trim()) {
        return prev.filter((m) => m.id !== "streaming");
      }
      return prev.map((m) =>
        m.id === "streaming" ? { ...m, id: `streamed-${Date.now()}` } : m,
      );
    });
  }, []);

  return {
    messages,
    setMessages,
    streaming,
    sendMessage,
    regenerateResponse,
    stopGeneration,
    connect,
  };
}
