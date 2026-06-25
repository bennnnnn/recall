import { useCallback, useEffect, useRef, useState } from 'react';

import { chatWebSocketUrl, Message } from '@/lib/api';

const CONNECT_TIMEOUT_MS = 8000;

type UseChatOptions = {
  /** Called with the new title when the server sends one after first reply */
  onFirstReply?: () => void;
};

export function useChat(
  token: string | null,
  chatId: string | null,
  options: UseChatOptions = {},
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const assistantBuffer = useRef('');
  const streamingRef = useRef(false);
  const firstReplyRef = useRef(false);
  const onFirstReplyRef = useRef(options.onFirstReply);
  onFirstReplyRef.current = options.onFirstReply;

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
    assistantBuffer.current = '';
    firstReplyRef.current = false;
    setStreaming(false);
  }, [chatId]);

  const connect = useCallback((): Promise<void> => {
    if (!token || !chatId) return Promise.resolve();
    if (wsRef.current?.readyState === WebSocket.OPEN) return Promise.resolve();

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    return new Promise((resolve, reject) => {
      const ws = new WebSocket(chatWebSocketUrl(chatId));
      wsRef.current = ws;

      const timer = setTimeout(() => {
        ws.close();
        reject(new Error('WebSocket connection timed out'));
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
        reject(new Error('WebSocket error'));
      };

      ws.onclose = () => {
        clearTimeout(timer);
        // If we were streaming when the connection dropped, stop gracefully
        if (streamingRef.current) {
          setStreaming(false);
          streamingRef.current = false;
          assistantBuffer.current = '';
          // Finalise any partial streaming bubble
          setMessages((prev) =>
            prev.map((m) =>
              m.id === 'streaming' ? { ...m, id: `streamed-${Date.now()}` } : m,
            ),
          );
        }
      };

      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data) as {
          type: string;
          content?: string;
          message?: string;
        };

        if (payload.type === 'token') {
          assistantBuffer.current += payload.content ?? '';
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === 'assistant' && last.id === 'streaming') {
              next[next.length - 1] = { ...last, content: assistantBuffer.current };
            } else {
              next.push({
                id: 'streaming',
                role: 'assistant',
                content: assistantBuffer.current,
                model: null,
                created_at: new Date().toISOString(),
              });
            }
            return next;
          });
        }

        if (payload.type === 'done') {
          setStreaming(false);
          streamingRef.current = false;
          assistantBuffer.current = '';
          setMessages((prev) =>
            prev.map((m) =>
              m.id === 'streaming' ? { ...m, id: `streamed-${Date.now()}` } : m,
            ),
          );
          // First reply done — background title generation may now be complete
          if (!firstReplyRef.current) {
            firstReplyRef.current = true;
            onFirstReplyRef.current?.();
          }
        }

        if (payload.type === 'error') {
          setStreaming(false);
          streamingRef.current = false;
        }
      };
    });
  }, [token, chatId]);

  const ensureConnected = useCallback(async () => {
    try {
      await connect();
    } catch {
      // Connection failed — caller will handle (send will be a no-op)
    }
  }, [connect]);

  const sendMessage = useCallback(
    async (content: string, model?: string) => {
      if (!token || !chatId) return;

      setMessages((prev) => [
        ...prev,
        {
          id: `local-${Date.now()}`,
          role: 'user',
          content,
          model: model ?? null,
          created_at: new Date().toISOString(),
        },
      ]);

      await ensureConnected();
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;

      setStreaming(true);
      streamingRef.current = true;
      assistantBuffer.current = '';
      wsRef.current.send(JSON.stringify({ type: 'message', content, model }));
    },
    [token, chatId, ensureConnected],
  );

  const regenerateResponse = useCallback(
    async (model?: string) => {
      if (!token || !chatId) return;

      setMessages((prev) => {
        const next = [...prev];
        if (next[next.length - 1]?.role === 'assistant') next.pop();
        return next;
      });

      await ensureConnected();
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;

      setStreaming(true);
      streamingRef.current = true;
      assistantBuffer.current = '';
      wsRef.current.send(JSON.stringify({ type: 'regenerate', model }));
    },
    [token, chatId, ensureConnected],
  );

  const stopGeneration = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: 'cancel' }));
    setStreaming(false);
    streamingRef.current = false;
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
