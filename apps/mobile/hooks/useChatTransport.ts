import { useCallback, useEffect, useRef } from "react";

import { chatWebSocketUrl } from "@/lib/api";
import type { ClientGeo } from "@/lib/clientGeo";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { shouldAbortPriorSse, streamChatMessageSse, streamChatRegenerateSse, type ChatSsePayload } from "@/lib/chat/sse";
import { EAGER_CONNECT_DEBOUNCE_MS } from "@/lib/chat/wsConnect";
import { ChatWsTransport, type ChatWsFallbackSignal } from "@/lib/chat/wsTransport";

type SendSseOptions = {
  attachmentIds?: string[];
  model?: string | null;
  clientGeo?: ClientGeo | null;
  ttftTurnId?: string | null;
};

type Options = {
  token: string | null;
  chatId: string | null;
  isCurrentView: () => boolean;
  ttftTurnId: () => string | null;
  onPayload: (boundChatId: string | null, payload: ChatSsePayload, ttftTurnId?: string | null) => void;
  onFallback: (transport: ChatWsTransport, signal: ChatWsFallbackSignal) => void;
  onSendFailure: (error: unknown, ttftTurnId: string | null) => void;
  onRegenerateFailure: () => void;
};

/**
 * WebSocket and SSE pipes for one chat view. Message state stays in useChat;
 * this hook only opens, sends, and tears down the connection.
 */
export function useChatTransport({
  token,
  chatId,
  isCurrentView,
  ttftTurnId,
  onPayload,
  onFallback,
  onSendFailure,
  onRegenerateFailure,
}: Options) {
  const wsTransportRef = useRef<ChatWsTransport | null>(null);
  const sseAbortRef = useRef<AbortController | null>(null);
  const sseAbortChatIdRef = useRef<string | null>(null);
  const isCurrentViewRef = useRef(isCurrentView);
  const ttftTurnIdRef = useRef(ttftTurnId);
  const onPayloadRef = useRef(onPayload);
  const onFallbackRef = useRef(onFallback);
  const onSendFailureRef = useRef(onSendFailure);
  const onRegenerateFailureRef = useRef(onRegenerateFailure);
  isCurrentViewRef.current = isCurrentView;
  ttftTurnIdRef.current = ttftTurnId;
  onPayloadRef.current = onPayload;
  onFallbackRef.current = onFallback;
  onSendFailureRef.current = onSendFailure;
  onRegenerateFailureRef.current = onRegenerateFailure;

  const beginSseStream = useCallback(() => {
    if (shouldAbortPriorSse(sseAbortChatIdRef.current, chatId)) {
      sseAbortRef.current?.abort();
    }
    const controller = new AbortController();
    sseAbortRef.current = controller;
    sseAbortChatIdRef.current = chatId;
    return controller.signal;
  }, [chatId]);

  const connect = useCallback((): Promise<void> => {
    if (!token || !chatId || !isCurrentViewRef.current()) return Promise.resolve();
    let transport = wsTransportRef.current;
    if (!transport) {
      transport = new ChatWsTransport({
        url: chatWebSocketUrl(chatId),
        token,
        clientTimezone: getDeviceTimezone(),
        onPayload: (payload) => {
          if (wsTransportRef.current !== transport) return;
          onPayloadRef.current(chatId, payload, ttftTurnIdRef.current());
        },
        onFallback: (signal) => onFallbackRef.current(transport!, signal),
      });
      wsTransportRef.current = transport;
    }
    return transport.connect();
  }, [token, chatId]);

  // Handshake overlaps reading. Debounced so flicking the chat list does not
  // open a socket per glance (each handshake counts against the connect limit).
  useEffect(() => {
    if (!token || !chatId) return;
    const timer = setTimeout(() => {
      void connect();
    }, EAGER_CONNECT_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [token, chatId, connect]);

  useEffect(() => {
    return () => {
      const transport = wsTransportRef.current;
      wsTransportRef.current = null;
      transport?.close();
    };
  }, []);

  const sendViaSse = useCallback(
    async (content: string, options?: SendSseOptions) => {
      if (!token || !chatId) return;
      const signal = beginSseStream();
      const turnId = options?.ttftTurnId ?? null;
      try {
        await streamChatMessageSse({
          token,
          chatId,
          content,
          attachmentIds: options?.attachmentIds,
          model: options?.model,
          clientGeo: options?.clientGeo,
          ttftTurnId: turnId,
          signal,
          onEvent: (payload) => {
            if (!signal.aborted && sseAbortRef.current?.signal === signal) {
              onPayloadRef.current(chatId, payload, turnId);
            }
          },
        });
      } catch (err) {
        if (!isCurrentViewRef.current() || signal.aborted || sseAbortRef.current?.signal !== signal) return;
        sseAbortRef.current = null;
        sseAbortChatIdRef.current = null;
        onSendFailureRef.current(err, turnId);
      }
    },
    [token, chatId, beginSseStream],
  );

  const regenerateViaSse = useCallback(
    async (model?: string | null, clientGeo?: ClientGeo | null) => {
      if (!token || !chatId) return;
      const signal = beginSseStream();
      try {
        await streamChatRegenerateSse({
          token,
          chatId,
          model,
          clientGeo,
          signal,
          onEvent: (payload) => {
            if (!signal.aborted && sseAbortRef.current?.signal === signal) {
              onPayloadRef.current(chatId, payload);
            }
          },
        });
      } catch {
        if (!isCurrentViewRef.current() || signal.aborted || sseAbortRef.current?.signal !== signal) return;
        sseAbortRef.current = null;
        sseAbortChatIdRef.current = null;
        onRegenerateFailureRef.current();
      }
    },
    [token, chatId, beginSseStream],
  );

  const currentSocket = useCallback(() => wsTransportRef.current, []);

  const dropSocket = useCallback(() => {
    const transport = wsTransportRef.current;
    wsTransportRef.current = null;
    transport?.close();
  }, []);

  /** Close the socket and forget an in-flight SSE without aborting it.
   * Stop is the only hard cancel; leaving a chat must let finalize drain. */
  const detach = useCallback(() => {
    dropSocket();
    sseAbortRef.current = null;
    sseAbortChatIdRef.current = null;
  }, [dropSocket]);

  const abortSse = useCallback(() => {
    sseAbortRef.current?.abort();
    sseAbortRef.current = null;
  }, []);

  const cancelSocket = useCallback(() => {
    wsTransportRef.current?.cancel();
  }, []);

  return {
    connect,
    sendViaSse,
    regenerateViaSse,
    currentSocket,
    dropSocket,
    detach,
    abortSse,
    cancelSocket,
  };
}

export type { ChatWsFallbackSignal };
