import { useCallback, useEffect, useRef } from "react";
import { AppState } from "react-native";

import { chatWebSocketUrl } from "@/lib/api";
import type { ClientGeo } from "@/lib/clientGeo";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { shouldAbortPriorSse, streamChatMessageSse, streamChatRegenerateSse, type ChatSsePayload } from "@/features/chat/model/sse";
import { createWsBackoff } from "@/features/chat/model/wsBackoff";
import { EAGER_CONNECT_DEBOUNCE_MS } from "@/features/chat/model/wsConnect";
import { ChatWsTransport, type ChatWsFallbackSignal } from "@/features/chat/model/wsTransport";

type SendSseOptions = {
  attachmentIds?: string[];
  model?: string | null;
  clientGeo?: ClientGeo | null;
  ttftTurnId?: string | null;
  /** The message's name from its socket send, so a replay of it runs once. */
  clientMessageId?: string;
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
  // A view's sockets share it, so a socket rebuilt after Stop keeps the
  // wait; opening a chat starts with none (`detach`).
  const backoffRef = useRef(createWsBackoff());
  const sseAbortRef = useRef<AbortController | null>(null);
  const sseAbortChatIdRef = useRef<string | null>(null);
  const isCurrentViewRef = useRef(isCurrentView);
  const ttftTurnIdRef = useRef(ttftTurnId);
  const onPayloadRef = useRef(onPayload);
  const onFallbackRef = useRef(onFallback);
  const onSendFailureRef = useRef(onSendFailure);
  const onRegenerateFailureRef = useRef(onRegenerateFailure);
  const backgroundedRef = useRef(false);
  const releasedInBackgroundRef = useRef(false);
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

  /** In the background an idle socket only answers the server's keepalive
   * pings, which wakes the radio every 20 seconds. A turn in flight keeps it
   * until its done or error; the next send or foreground opens a new one. */
  const releaseIdleInBackground = useCallback(() => {
    const transport = wsTransportRef.current;
    if (!backgroundedRef.current || !transport || transport.isTurnActive()) return;
    wsTransportRef.current = null;
    releasedInBackgroundRef.current = true;
    transport.close();
  }, []);

  const connect = useCallback((): Promise<void> => {
    if (!token || !chatId || !isCurrentViewRef.current()) return Promise.resolve();
    let transport = wsTransportRef.current;
    if (!transport) {
      transport = new ChatWsTransport({
        url: chatWebSocketUrl(chatId),
        token,
        clientTimezone: getDeviceTimezone(),
        backoff: backoffRef.current,
        onPayload: (payload) => {
          if (wsTransportRef.current !== transport) return;
          onPayloadRef.current(chatId, payload, ttftTurnIdRef.current());
          releaseIdleInBackground();
        },
        onFallback: (signal) => onFallbackRef.current(transport!, signal),
      });
      wsTransportRef.current = transport;
    }
    return transport.connect();
  }, [token, chatId, releaseIdleInBackground]);

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

  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "background") {
        backgroundedRef.current = true;
        releaseIdleInBackground();
        return;
      }
      if (state !== "active") return;
      backgroundedRef.current = false;
      // A turn kept its socket in the background, where the radio may have dropped it.
      const kept = wsTransportRef.current;
      if (kept?.isTurnActive()) kept.probe();
      if (!releasedInBackgroundRef.current) return;
      releasedInBackgroundRef.current = false;
      // Same head start as opening the chat: the handshake overlaps reading.
      void connect();
    });
    return () => sub.remove();
  }, [connect, releaseIdleInBackground]);

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
          clientMessageId: options?.clientMessageId,
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
   * Stop is the only hard cancel; leaving a chat must let finalize drain.
   * The next view tries the socket at once, whatever failed in this one. */
  const detach = useCallback(() => {
    dropSocket();
    backoffRef.current = createWsBackoff();
    sseAbortRef.current = null;
    sseAbortChatIdRef.current = null;
  }, [dropSocket]);

  const abortSse = useCallback(() => {
    sseAbortRef.current?.abort();
    sseAbortRef.current = null;
  }, []);

  /** `shownChars`: how much of the reply the phone kept on screen (see ChatWsTransport.cancel). */
  const cancelSocket = useCallback((shownChars?: number) => {
    wsTransportRef.current?.cancel(shownChars);
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
