import { useCallback, useEffect, useRef, type MutableRefObject } from "react";
import { AppState } from "react-native";
import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";
import { useFocusEffect } from "expo-router";

import { useAccountSession } from "@/contexts/accountSession";
import { chatWebSocketUrl } from "@/lib/api";
import { accessTokenNeedsRefresh, freshAccessToken } from "@/lib/api/client";
import type { ClientGeo } from "@/features/chat/model/clientGeo";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { isNetworkPathChange } from "@/lib/networkStatus";
import { shouldAbortPriorSse, streamChatMessageSse, streamChatRegenerateSse, type ChatSsePayload } from "@/features/chat/model/sse";
import { createWsBackoff, type WsBackoff } from "@/features/chat/model/wsBackoff";
import { ChatWsTransport, type ChatWsFallbackSignal } from "@/features/chat/model/wsTransport";
import { useLatestRef } from "@/lib/latestRef";

type SendSseOptions = {
  attachmentIds?: string[];
  model?: string | null;
  clientGeo?: ClientGeo | null;
  ttftTurnId?: string | null;
  /** The message's name from its socket send, so a replay of it runs once. */
  clientMessageId?: string;
};

/** Nothing more is coming on this socket: no turn, and no follow-up questions due. */
function isQuiet(transport: ChatWsTransport): boolean {
  return !transport.isTurnActive() && !transport.expectsFollowUps();
}

type SocketRefs = {
  wsTransportRef: MutableRefObject<ChatWsTransport | null>;
  backoffRef: MutableRefObject<WsBackoff>;
};

/**
 * When a chat's socket goes with no send to make: the view unmounts, a screen covers the
 * chat (To-do, Settings, Library), the app goes to the background, or the network path
 * changes (a turn in flight is probed instead). Returns what a new transport reads: whether
 * the chat is in view, and the release a frame received in the background runs.
 */
function useSocketLeaves({ wsTransportRef, backoffRef }: SocketRefs) {
  const backgroundedRef = useRef(false);
  /** The chat is the screen on top (no To-do, Settings or Library over it). */
  const inViewRef = useRef(true);

  /** In the background an idle socket only answers the server's keepalive
   * pings, which wakes the radio every 20 seconds. A turn in flight keeps it
   * until its done or error; the next send opens a new one. */
  const releaseIdleInBackground = useCallback(() => {
    const transport = wsTransportRef.current;
    if (!backgroundedRef.current || !transport || transport.isTurnActive()) return;
    wsTransportRef.current = null;
    transport.close();
  }, [wsTransportRef]);

  useEffect(() => {
    return () => {
      const transport = wsTransportRef.current;
      wsTransportRef.current = null;
      transport?.close();
    };
  }, [wsTransportRef]);

  // A screen over the chat (To-do, Settings, Library): its socket goes once nothing is due.
  useFocusEffect(useCallback(() => {
    inViewRef.current = true;
    return () => {
      inViewRef.current = false;
      wsTransportRef.current?.leftView();
    };
  }, [wsTransportRef]));

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
    });
    return () => sub.remove();
  }, [wsTransportRef, releaseIdleInBackground]);

  // Wi-Fi ⇄ cellular, or back online: a socket opened on the old path can be
  // half-open. A turn's socket is probed (dropped if it does not answer); one
  // with no turn is closed, and the next send opens one on the new path.
  // Failures on the old path do not hold the new one back.
  useEffect(() => {
    let previous: NetInfoState | null = null;
    return NetInfo.addEventListener((state) => {
      const changed = isNetworkPathChange(previous, state);
      previous = state;
      if (!changed || backgroundedRef.current) return;
      backoffRef.current = createWsBackoff();
      const transport = wsTransportRef.current;
      if (transport?.isTurnActive()) {
        transport.probe();
        return;
      }
      wsTransportRef.current = null;
      transport?.close();
    });
  }, [wsTransportRef, backoffRef]);

  return { inViewRef, releaseIdleInBackground };
}

type Options = {
  chatId: string | null;
  isCurrentView: () => boolean;
  ttftTurnId: () => string | null;
  onPayload: (boundChatId: string | null, payload: ChatSsePayload, ttftTurnId?: string | null) => void;
  onFallback: (transport: ChatWsTransport, signal: ChatWsFallbackSignal) => void;
  onSendFailure: (error: unknown, ttftTurnId: string | null) => void;
  onRegenerateFailure: (error: unknown) => void;
};

/**
 * WebSocket and SSE pipes for one chat view. Message state stays in useChat;
 * this hook only opens, sends, and tears down the connection. A socket lives as
 * long as its use: a send opens it (`connect`), the conversation's next messages
 * reuse it, and it closes itself a minute after its last turn
 * (`ChatWsTransport.releaseWhenQuiet`), or as soon as the user leaves the chat:
 * another chat (`detach`), a screen over it, the background. Reading a chat,
 * typing in it or switching chats opens none (2026-11-08 feature test: 49 opens in
 * 48 turns, and an idle one left behind each chat the user moved on from).
 */
export function useChatTransport({
  chatId,
  isCurrentView,
  ttftTurnId,
  onPayload,
  onFallback,
  onSendFailure,
  onRegenerateFailure,
}: Options) {
  // Keyed on the account, not the bearer token: the token rotates hourly, and the
  // socket reads the newest one when it connects (code-health audit NET-11, NET-12).
  const { account, getToken } = useAccountSession();
  const wsTransportRef = useRef<ChatWsTransport | null>(null);
  /** The token the current transport authenticates with. */
  const transportTokenRef = useRef<string | null>(null);
  // A view's sockets share it, so a socket rebuilt after Stop or a token
  // refresh keeps the wait; opening a chat starts with none (`detach`).
  const backoffRef = useRef(createWsBackoff());
  const sseAbortRef = useRef<AbortController | null>(null);
  const sseAbortChatIdRef = useRef<string | null>(null);
  const { inViewRef, releaseIdleInBackground } = useSocketLeaves({ wsTransportRef, backoffRef });
  const isCurrentViewRef = useLatestRef(isCurrentView);
  const ttftTurnIdRef = useLatestRef(ttftTurnId);
  const onPayloadRef = useLatestRef(onPayload);
  const onFallbackRef = useLatestRef(onFallback);
  const onSendFailureRef = useLatestRef(onSendFailure);
  const onRegenerateFailureRef = useLatestRef(onRegenerateFailure);

  const beginSseStream = useCallback(() => {
    if (shouldAbortPriorSse(sseAbortChatIdRef.current, chatId)) {
      sseAbortRef.current?.abort();
    }
    const controller = new AbortController();
    sseAbortRef.current = controller;
    sseAbortChatIdRef.current = chatId;
    return controller.signal;
  }, [chatId]);

  const openSocket = useCallback((): Promise<void> => {
    const token = getToken();
    if (!account || !token || !chatId || !isCurrentViewRef.current()) return Promise.resolve();
    let transport = wsTransportRef.current;
    if (transport && transportTokenRef.current !== token && isQuiet(transport)) {
      // The server checks a socket's own token on every send: after a refresh
      // the old one is refused and the send goes over SSE. A new socket instead.
      wsTransportRef.current = null;
      transport.close();
      transport = null;
    }
    if (!transport) {
      transport = new ChatWsTransport({
        url: chatWebSocketUrl(chatId),
        getToken,
        clientTimezone: getDeviceTimezone,
        backoff: backoffRef.current,
        inView: () => inViewRef.current,
        onPayload: (payload) => {
          if (wsTransportRef.current !== transport) return;
          onPayloadRef.current(chatId, payload, ttftTurnIdRef.current());
          releaseIdleInBackground();
        },
        onFallback: (signal) => onFallbackRef.current(transport!, signal),
      });
      wsTransportRef.current = transport;
      transportTokenRef.current = token;
    }
    return transport.connect();
  }, [
    account, chatId, getToken, releaseIdleInBackground, inViewRef, isCurrentViewRef, onFallbackRef, onPayloadRef,
    ttftTurnIdRef,
  ]);

  const connect = useCallback((): Promise<void> => {
    const token = getToken();
    if (!account || !token) return Promise.resolve();
    // An expired token is refreshed before the handshake, not refused after it.
    if (!accessTokenNeedsRefresh(token)) return openSocket();
    return freshAccessToken(token).then((fresh) => (fresh ? openSocket() : undefined));
  }, [account, getToken, openSocket]);
  const sendViaSse = useCallback(
    async (content: string, options?: SendSseOptions) => {
      const token = getToken();
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
    [getToken, chatId, beginSseStream, isCurrentViewRef, onPayloadRef, onSendFailureRef],
  );

  const regenerateViaSse = useCallback(
    async (model?: string | null, clientGeo?: ClientGeo | null) => {
      const token = getToken();
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
      } catch (err) {
        if (!isCurrentViewRef.current() || signal.aborted || sseAbortRef.current?.signal !== signal) return;
        sseAbortRef.current = null;
        sseAbortChatIdRef.current = null;
        onRegenerateFailureRef.current(err);
      }
    },
    [getToken, chatId, beginSseStream, isCurrentViewRef, onPayloadRef, onRegenerateFailureRef],
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
