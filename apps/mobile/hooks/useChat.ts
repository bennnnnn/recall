import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { chatWebSocketUrl, Message } from "@/lib/api";
import { streamChatMessageSse, streamChatRegenerateSse, isSseAbortError, shouldAbortPriorSse, type ChatSsePayload } from "@/lib/chatSse";
import { clientGeoWsFields, type ClientGeo } from "@/lib/clientGeo";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
import { getSessionGeneration } from "@/lib/auth";
import {
  applyStreamEndModel,
  buildDoneMergeInput,
  mergeDoneIntoMessages,
  parseChatWsPayload,
  shouldIgnoreStoppedStreamEvent,
} from "@/lib/chatSocketReduce";
import {
  publishStreamingDraft,
  type StreamingDraft,
} from "@/lib/streamingDraftStore";
import {
  popLastAssistantMessage,
  restoreAssistantMessage,
} from "@/lib/chatRegenerateLogic";
import { replaceStreamingMessageWithPartial } from "@/lib/chatPartialStream";
import {
  EAGER_CONNECT_DEBOUNCE_MS,
  WS_CONNECT_TIMEOUT_MS,
} from "@/lib/chatWsConnect";

export type { StreamingDraft };

type SendMessageOptions = {
  skipUserBubble?: boolean;
  trackSendingMessageId?: string;
  attachmentIds?: string[];
  localImageUri?: string | null;
  localFileUri?: string | null;
  localFileName?: string | null;
  localFileContentType?: string | null;
  model?: string | null;
  clientGeo?: ClientGeo | null;
};

type PendingSend = {
  content: string;
  options: SendMessageOptions;
  messageId: string | null;
  retryingRejected: boolean;
  dispatched: boolean;
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
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const messagesRef = useRef<Message[]>([]);
  messagesRef.current = messages;
  const [streaming, setStreaming] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [sendingMessageId, setSendingMessageId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const wsTurnRef = useRef<WebSocket | null>(null);
  const wsAuthFallbackRef = useRef<{ socket: WebSocket; retry: () => Promise<void> } | null>(null);
  const sendAttemptRef = useRef(0);
  const pendingSendRef = useRef<PendingSend | null>(null);
  // Only explicit pre-persistence rejections belong here. Keep them across
  // conversation switches and newer sends until the user retries or stops.
  const rejectedSendsRef = useRef(new Map<string, PendingSend[]>());
  const [rejectedSend, setRejectedSend] = useState<{ content: string } | null>(null);
  const mountedRef = useRef(true);
  const connectingRef = useRef<Promise<void> | null>(null);
  const preferSseRef = useRef(false);
  const sseAbortRef = useRef<AbortController | null>(null);
  const sseAbortChatIdRef = useRef<string | null>(null);
  const viewingChatIdRef = useRef(chatId);
  viewingChatIdRef.current = chatId;
  const authenticated = token != null;
  const sessionGeneration = getSessionGeneration();
  const rejectedSessionRef = useRef(sessionGeneration);
  // A -> B -> A is a new view: old callbacks for A must stay detached.
  const viewIdentity = useMemo(() => ({ chatId, authenticated, sessionGeneration }), [chatId, authenticated, sessionGeneration]);
  const activeViewRef = useRef(viewIdentity);
  activeViewRef.current = viewIdentity;
  const isCurrentView = useCallback(
    () => mountedRef.current && activeViewRef.current === viewIdentity && getSessionGeneration() === viewIdentity.sessionGeneration,
    [viewIdentity],
  );
  const assistantBuffer = useRef("");
  const streamingDraftRef = useRef<StreamingDraft | null>(null);
  const draftRafRef = useRef<number | null>(null);
  const streamingRef = useRef(false);
  const finalizingRef = useRef(false);
  /** Prior assistant reply kept until regenerate succeeds or is rolled back. */
  const regenerateBackupRef = useRef<Message | null>(null);
  const regenerateUiActiveRef = useRef(false);
  /**
   * When the user stops generation, the streaming bubble is committed locally
   * as `streamed-<ts>`. We track that id so the server's late `done` event
   * reconciles it in place (authoritative id + final_content) instead of
   * appending a duplicate. Cleared on done/error/chat-switch.
   */
  const stoppedStreamedIdRef = useRef<string | null>(null);

  const flushStreamingDraft = useCallback(() => {
    draftRafRef.current = null;
    publishStreamingDraft(streamingDraftRef.current);
  }, []);

  const updateStreamingDraft = useCallback(
    (draft: StreamingDraft | null) => {
      streamingDraftRef.current = draft;
      if (draft === null) {
        if (draftRafRef.current != null) {
          cancelAnimationFrame(draftRafRef.current);
          draftRafRef.current = null;
        }
        publishStreamingDraft(null);
        return;
      }
      if (draftRafRef.current == null) {
        draftRafRef.current = requestAnimationFrame(flushStreamingDraft);
      }
    },
    [flushStreamingDraft],
  );
  const firstReplyRef = useRef(false);
  const onFirstReplyRef = useRef(options.onFirstReply);
  const onErrorRef = useRef(options.onError);
  const onTodosSyncRef = useRef(options.onTodosSync);
  // Pending todo-sync follow-up timers (the post-done 2.5s/7s refreshes). Held
  // here so they can be cancelled on chat switch / unmount — otherwise a slow
  // timer from chat A fires `onTodosSync` after we've moved to chat B.
  const todoSyncTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const clearTodoSyncTimers = useCallback(() => {
    for (const id of todoSyncTimersRef.current) clearTimeout(id);
    todoSyncTimersRef.current = [];
  }, []);
  onFirstReplyRef.current = options.onFirstReply;
  onErrorRef.current = options.onError;
  onTodosSyncRef.current = options.onTodosSync;

  const reportError = useCallback((message: string, code?: string) => {
    onErrorRef.current?.(message, code);
  }, []);

  const beginSseStream = useCallback(() => {
    if (shouldAbortPriorSse(sseAbortChatIdRef.current, chatId)) {
      sseAbortRef.current?.abort();
    }
    const controller = new AbortController();
    sseAbortRef.current = controller;
    sseAbortChatIdRef.current = chatId;
    return controller.signal;
  }, [chatId]);

  const clearStreamingBubble = useCallback(() => {
    updateStreamingDraft(null);
    setFinalizing(false);
    setMessages((prev) => prev.filter((m) => m.id !== "streaming"));
  }, [updateStreamingDraft]);

  const restoreRegenerateBackup = useCallback(() => {
    if (!isCurrentView()) return;
    regenerateUiActiveRef.current = false;
    const backup = regenerateBackupRef.current;
    regenerateBackupRef.current = null;
    clearStreamingBubble();
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    finalizingRef.current = false;
    if (backup) {
      setMessages((prev) => restoreAssistantMessage(prev, backup));
    }
  }, [clearStreamingBubble, isCurrentView]);

  const appendStreamingPlaceholder = useCallback(() => {
    setMessages((prev) => {
      if (prev.some((m) => m.id === "streaming")) return prev;
      return [
        ...prev,
        {
          id: "streaming",
          renderKey: `stream-${Date.now()}`,
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
    finalizingRef.current = finalizing;
  }, [finalizing]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (draftRafRef.current != null) {
        cancelAnimationFrame(draftRafRef.current);
      }
      clearTodoSyncTimers();
      updateStreamingDraft(null);
      // Do not abort SSE on unmount — New chat / leave must drain like WS.
      const socket = wsRef.current;
      wsRef.current = null;
      socket?.close();
    };
  }, [clearTodoSyncTimers, updateStreamingDraft]);

  // Close and reset socket when chat changes. Do not abort SSE — Stop is the
  // only hard cancel. Leftover SSE events are ignored via viewingChatIdRef.
  useEffect(() => {
    const socket = wsRef.current;
    wsRef.current = null;
    socket?.close();
    wsTurnRef.current = null;
    wsAuthFallbackRef.current = null;
    sendAttemptRef.current += 1;
    const pendingRetry = pendingSendRef.current;
    if (pendingRetry?.retryingRejected && !pendingRetry.dispatched) {
      setMessages((previous) => previous.filter((message) => message.id !== pendingRetry.messageId));
    }
    pendingSendRef.current = null;
    if (rejectedSessionRef.current !== sessionGeneration) {
      rejectedSendsRef.current.clear();
      rejectedSessionRef.current = sessionGeneration;
    }
    setRejectedSend(chatId ? rejectedSendsRef.current.get(chatId)?.[0] ?? null : null);
    // Detach the old fetch without aborting its server-side finalization.
    sseAbortRef.current = null;
    sseAbortChatIdRef.current = null;
    connectingRef.current = null;
    preferSseRef.current = false;
    assistantBuffer.current = "";
    firstReplyRef.current = false;
    regenerateBackupRef.current = null;
    stoppedStreamedIdRef.current = null;
    regenerateUiActiveRef.current = false;
    clearTodoSyncTimers();
    updateStreamingDraft(null);
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    finalizingRef.current = false;
    setSendingMessageId(null);
  }, [viewIdentity, chatId, sessionGeneration, updateStreamingDraft, clearTodoSyncTimers]);

  const handleChatPayload = useCallback(
    (payload: ChatSsePayload) => {
      if (shouldIgnoreStoppedStreamEvent(payload.type, streamingRef.current)) {
        return;
      }
      if (payload.type === "start") {
        wsAuthFallbackRef.current = null;
        setSendingMessageId(null);
        setFinalizing(false);
        setStreaming(true);
        streamingRef.current = true;
        assistantBuffer.current = "";
        // Keep the instant local status (set at send time) instead of
        // blanking the label until the server's first status event.
        updateStreamingDraft({
          content: "",
          status: streamingDraftRef.current?.status,
          statusDetail: streamingDraftRef.current?.statusDetail,
        });
        appendStreamingPlaceholder();
      }

      if (payload.type === "status" && typeof payload.phase === "string") {
        updateStreamingDraft({
          content: assistantBuffer.current,
          search_sources: streamingDraftRef.current?.search_sources,
          status: payload.phase,
          statusDetail:
            typeof payload.detail === "string" && payload.detail
              ? payload.detail
              : undefined,
        });
      }

      // `reasoning` events are ignored — CoT is not the answer; status/waiting
      // already covers "the model is working".

      if (payload.type === "token") {
        pendingSendRef.current = null;
        assistantBuffer.current += payload.content ?? "";
        updateStreamingDraft({
          content: assistantBuffer.current,
          search_sources: streamingDraftRef.current?.search_sources,
          status: undefined,
          statusDetail: undefined,
        });
      }

      if (payload.type === "stream_end") {
        pendingSendRef.current = null;
        setFinalizing(true);
        if (typeof payload.resolved_model === "string" && payload.resolved_model) {
          setMessages((prev) => applyStreamEndModel(prev, payload.resolved_model));
        }
      }

      if (payload.type === "done") {
        pendingSendRef.current = null;
        regenerateUiActiveRef.current = false;
        wsAuthFallbackRef.current = null;
        wsTurnRef.current = null;
        regenerateBackupRef.current = null;
        setSendingMessageId(null);
        const stoppedId = stoppedStreamedIdRef.current;
        stoppedStreamedIdRef.current = null;
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        finalizingRef.current = false;
        assistantBuffer.current = "";
        const draft = streamingDraftRef.current;
        updateStreamingDraft(null);
        setMessages((prev) =>
          mergeDoneIntoMessages(
            prev,
            buildDoneMergeInput(payload, draft, undefined, stoppedId),
          ),
        );
        if (!firstReplyRef.current) {
          firstReplyRef.current = true;
          onFirstReplyRef.current?.();
        }
        if (payload.todos_sync === "1") {
          onTodosSyncRef.current?.();
          // Background Schedule extract can lag; refresh again so Schedule catches up.
          // Tracked so they're cancelled on chat switch / unmount (no firing on the
          // wrong chat after navigating away).
          clearTodoSyncTimers();
          todoSyncTimersRef.current.push(setTimeout(() => onTodosSyncRef.current?.(), 2500));
          todoSyncTimersRef.current.push(setTimeout(() => onTodosSyncRef.current?.(), 7000));
        }
      }

      if (payload.type === "error") {
        // Both transports send start before attempting the prepare lock. Busy
        // is the explicit guarantee this new user turn was never persisted.
        const rejected = payload.code === "busy" ? pendingSendRef.current : null;
        pendingSendRef.current = null;
        if (rejected && chatId) {
          const queue = rejectedSendsRef.current.get(chatId) ?? [];
          if (rejected.retryingRejected) queue.unshift(rejected);
          else queue.push(rejected);
          rejectedSendsRef.current.set(chatId, queue);
          setRejectedSend(queue[0]);
          setMessages((previous) => previous.filter((message) =>
            message.id !== rejected.messageId || message.role !== "user"));
        }
        regenerateUiActiveRef.current = false;
        wsAuthFallbackRef.current = null;
        wsTurnRef.current = null;
        stoppedStreamedIdRef.current = null;
        setSendingMessageId(null);
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        finalizingRef.current = false;
        const draft = streamingDraftRef.current;
        const partial = (draft?.content ?? assistantBuffer.current).trim();
        assistantBuffer.current = "";
        if (regenerateBackupRef.current) {
          restoreRegenerateBackup();
        } else if (partial) {
          // Keep what the user already saw (same idea as stop / disconnect).
          const keptId = `streamed-${Date.now()}`;
          updateStreamingDraft(null);
          setMessages((prev) => {
            const streamingMsg = prev.find((m) => m.id === "streaming");
            if (!streamingMsg) return prev;
            return prev.map((m) =>
              m.id === "streaming"
                ? {
                    ...m,
                    id: keptId,
                    content: partial,
                    search_sources: draft?.search_sources ?? m.search_sources,
                    generationStopped: true,
                  }
                : m,
            );
          });
          stoppedStreamedIdRef.current = keptId;
        } else {
          clearStreamingBubble();
        }
        reportError(
          payload.message ?? t("chat.error_generic"),
          rejected ? "send_rejected" : typeof payload.code === "string" ? payload.code : undefined,
        );
      }
    },
    [
      appendStreamingPlaceholder,
      chatId,
      clearStreamingBubble,
      restoreRegenerateBackup,
      reportError,
      updateStreamingDraft,
      clearTodoSyncTimers,
      t,
    ],
  );

  const handleChatPayloadForChat = useCallback(
    (boundChatId: string | null, payload: ChatSsePayload) => {
      if (!isCurrentView() || viewingChatIdRef.current !== boundChatId) return;
      handleChatPayload(payload);
    },
    [handleChatPayload, isCurrentView],
  );

  const preservePartialStream = useCallback((): boolean => {
    const draft = streamingDraftRef.current;
    const partial = (draft?.content ?? assistantBuffer.current).trim();
    assistantBuffer.current = "";
    if (!partial) return false;

    const keptId = `streamed-${Date.now()}`;
    updateStreamingDraft(null);
    setMessages((prev) =>
      replaceStreamingMessageWithPartial(prev, partial, draft, keptId),
    );
    return true;
  }, [updateStreamingDraft]);

  const connect = useCallback((): Promise<void> => {
    if (!token || !chatId || !isCurrentView()) return Promise.resolve();
    if (preferSseRef.current) return Promise.resolve();
    if (wsRef.current?.readyState === WebSocket.OPEN) return Promise.resolve();
    // Reuse an in-flight connection so concurrent callers don't tear each other down
    if (connectingRef.current) return connectingRef.current;

    if (wsRef.current) {
      const socket = wsRef.current;
      wsRef.current = null;
      socket.close();
    }

    const connectPromise = new Promise<void>((resolve) => {
      const ws = new WebSocket(chatWebSocketUrl(chatId));
      wsRef.current = ws;
      const isCurrentSocket = () => isCurrentView() && wsRef.current === ws;

      const timer = setTimeout(() => {
        if (isCurrentSocket()) {
          wsRef.current = null;
          preferSseRef.current = true;
        }
        resolve();
        ws.close();
      }, WS_CONNECT_TIMEOUT_MS);

      ws.onopen = () => {
        clearTimeout(timer);
        if (!isCurrentSocket()) {
          resolve();
          ws.close();
          return;
        }
        ws.send(
          JSON.stringify({
            token,
            client_timezone: getDeviceTimezone(),
          }),
        );
        resolve();
      };

      const disconnect = () => {
        clearTimeout(timer);
        resolve();
        if (!isCurrentSocket()) return;
        wsRef.current = null;
        // SSE shares REST's token refresh when WS authentication fails.
        preferSseRef.current = true;
        // A failed handshake must let the waiting send fall back to SSE.
        if (wsTurnRef.current !== ws) return;
        wsTurnRef.current = null;
        pendingSendRef.current = null;
        if (streamingRef.current || finalizingRef.current) {
          setStreaming(false);
          setFinalizing(false);
          streamingRef.current = false;
          finalizingRef.current = false;
          const hadContent = assistantBuffer.current.trim().length > 0;
          const draft = streamingDraftRef.current;
          const failedRegenerateBackup = regenerateBackupRef.current;
          regenerateBackupRef.current = null;
          assistantBuffer.current = "";
          updateStreamingDraft(null);
          setSendingMessageId(null);
          setMessages((prev) => {
            const streamingMsg = prev.find((m) => m.id === "streaming");
            if (!streamingMsg) return prev;
            if (!hadContent) {
              const withoutStreaming = prev.filter((m) => m.id !== "streaming");
              if (failedRegenerateBackup) {
                return restoreAssistantMessage(withoutStreaming, failedRegenerateBackup);
              }
              return withoutStreaming;
            }
            return prev.map((m) =>
              m.id === "streaming"
                ? {
                    ...m,
                    id: `streamed-${Date.now()}`,
                    content: draft?.content ?? m.content,
                    search_sources: draft?.search_sources ?? m.search_sources,
                    generationStopped: true,
                  }
                : m,
            );
          });
          if (!hadContent && !failedRegenerateBackup) {
            reportError(t("chat.error_connection_lost"));
          }
        }
      };

      ws.onclose = disconnect;
      ws.onerror = () => {
        disconnect();
        ws.close();
      };

      ws.onmessage = (event) => {
        if (!isCurrentSocket()) return;
        const payload = parseChatWsPayload(String(event.data));
        if (!payload) return;
        // The server rejects auth before accepting the turn. Only this
        // explicit rejection is safe to replay through REST's token refresh.
        if (payload.type === "error" && payload.message === "Unauthorized") {
          const fallback = wsAuthFallbackRef.current;
          if (!fallback && wsTurnRef.current === ws) {
            handleChatPayloadForChat(chatId, payload);
            return;
          }
          wsAuthFallbackRef.current = null;
          wsTurnRef.current = null;
          wsRef.current = null;
          preferSseRef.current = true;
          ws.close();
          if (fallback?.socket === ws) void fallback.retry();
          return;
        }
        handleChatPayloadForChat(chatId, payload);
      };
    });

    connectingRef.current = connectPromise;
    connectPromise.then(
      () => {
        if (connectingRef.current === connectPromise) connectingRef.current = null;
      },
      () => {
        if (connectingRef.current === connectPromise) connectingRef.current = null;
      },
    );
    return connectPromise;
  }, [
    token,
    chatId,
    reportError,
    handleChatPayloadForChat,
    updateStreamingDraft,
    isCurrentView,
    t,
  ]);

  // Eagerly open the WebSocket once the user has settled on a chat, so the
  // handshake + auth frame overlap with reading/typing instead of sitting on
  // the first send. Debounced so quickly flicking through the chat list
  // doesn't fire a connect+auth+close cycle per chat glanced at (each open
  // WS handshake counts against the server's per-user connect rate limit).
  useEffect(() => {
    if (!token || !chatId) return;
    const timer = setTimeout(() => {
      void connect();
    }, EAGER_CONNECT_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [token, chatId, connect]);

  const sendViaSse = useCallback(
    async (
      content: string,
      options?: {
        attachmentIds?: string[];
        model?: string | null;
        clientGeo?: ClientGeo | null;
      },
    ) => {
      if (!token || !chatId) return;
      const signal = beginSseStream();
      try {
        await streamChatMessageSse({
          token,
          chatId,
          content,
          attachmentIds: options?.attachmentIds,
          model: options?.model,
          clientGeo: options?.clientGeo,
          signal,
          onEvent: (payload) => {
            if (!signal.aborted && sseAbortRef.current?.signal === signal) {
              handleChatPayloadForChat(chatId, payload);
            }
          },
        });
      } catch (err) {
        if (!isCurrentView() || signal.aborted || sseAbortRef.current?.signal !== signal || isSseAbortError(err)) return;
        pendingSendRef.current = null;
        setSendingMessageId(null);
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        finalizingRef.current = false;
        if (!preservePartialStream()) {
          clearStreamingBubble();
        }
        reportError(t("chat.error_unreachable"));
      }
    },
    [
      token,
      chatId,
      beginSseStream,
      handleChatPayloadForChat,
      preservePartialStream,
      clearStreamingBubble,
      reportError,
      isCurrentView,
      t,
    ],
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
              handleChatPayloadForChat(chatId, payload);
            }
          },
        });
      } catch (err) {
        if (!isCurrentView() || signal.aborted || sseAbortRef.current?.signal !== signal || isSseAbortError(err)) return;
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        finalizingRef.current = false;
        if (preservePartialStream()) {
          regenerateBackupRef.current = null;
        } else {
          restoreRegenerateBackup();
        }
        reportError(t("chat.error_unreachable"));
      }
    },
    [
      token,
      chatId,
      beginSseStream,
      handleChatPayloadForChat,
      preservePartialStream,
      restoreRegenerateBackup,
      reportError,
      isCurrentView,
      t,
    ],
  );

  const ensureConnected = useCallback(async () => {
    try {
      await connect();
    } catch {
      reportError(t("chat.error_unreachable"));
    }
  }, [connect, reportError, t]);

  const dispatchSend = useCallback(
    async (
      content: string,
      options?: SendMessageOptions,
      rejectedRetry?: PendingSend,
    ) => {
      if (!token || !chatId || !isCurrentView() || streamingRef.current || finalizingRef.current) return;
      const attempt = ++sendAttemptRef.current;
      // Stop may still have a final frame in flight. A fresh connection keeps
      // that old frame from finalizing the next turn's placeholder.
      if (stoppedStreamedIdRef.current) {
        const socket = wsRef.current;
        wsRef.current = null;
        connectingRef.current = null;
        socket?.close();
        stoppedStreamedIdRef.current = null;
      }

      let trackedId = options?.trackSendingMessageId ?? null;
      if (!options?.skipUserBubble) {
        trackedId = `local-${Date.now()}-${attempt}`;
        setMessages((prev) => [
          ...prev,
          {
            id: trackedId!,
            role: "user",
            content,
            model: null,
            local_image_uri: options?.localImageUri ?? null,
            local_file_uri: options?.localFileUri ?? null,
            local_file_name: options?.localFileName ?? null,
            local_file_content_type: options?.localFileContentType ?? null,
            created_at: new Date().toISOString(),
          },
        ]);
      }
      pendingSendRef.current = {
        content,
        messageId: trackedId,
        retryingRejected: rejectedRetry != null,
        dispatched: false,
        options: {
          ...options,
          skipUserBubble: false,
          trackSendingMessageId: undefined,
          attachmentIds: options?.attachmentIds?.slice(),
          clientGeo: options?.clientGeo ? { ...options.clientGeo } : options?.clientGeo,
        },
      };
      assistantBuffer.current = "";
      // Typing dots immediately — don't wait for the socket or server `start`,
      // and don't leave "Sending" on the user bubble while we connect.
      if (!streamingRef.current) {
        setStreaming(true);
        streamingRef.current = true;
        setSendingMessageId(null);
        updateStreamingDraft({
          content: "",
          status: options?.attachmentIds?.length ? "reading_files" : undefined,
        });
        appendStreamingPlaceholder();
      } else if (trackedId) {
        setSendingMessageId(trackedId);
      }

      await ensureConnected();
      if (!isCurrentView() || sendAttemptRef.current !== attempt) return;
      if (rejectedRetry) {
        // Keep recovery available while the handshake is pending: navigation
        // can still prevent dispatch. Consume it only when sending can begin.
        const queue = rejectedSendsRef.current.get(chatId);
        const index = queue?.indexOf(rejectedRetry) ?? -1;
        if (queue && index >= 0) queue.splice(index, 1);
        if (!queue?.length) rejectedSendsRef.current.delete(chatId);
        setRejectedSend(queue?.[0] ?? null);
      }
      if (pendingSendRef.current) pendingSendRef.current.dispatched = true;

      if (preferSseRef.current || wsRef.current?.readyState !== WebSocket.OPEN) {
        await sendViaSse(content, {
          attachmentIds: options?.attachmentIds,
          model: options?.model,
          clientGeo: options?.clientGeo,
        });
        return;
      }

      wsTurnRef.current = wsRef.current;
      wsAuthFallbackRef.current = {
        socket: wsRef.current,
        retry: () => sendViaSse(content, {
          attachmentIds: options?.attachmentIds,
          model: options?.model,
          clientGeo: options?.clientGeo,
        }),
      };
      wsRef.current.send(
        JSON.stringify({
          type: "message",
          content,
          attachment_ids: options?.attachmentIds ?? [],
          model: options?.model ?? null,
          ...clientGeoWsFields(options?.clientGeo),
        }),
      );
    },
    [token, chatId, ensureConnected, appendStreamingPlaceholder, updateStreamingDraft, sendViaSse, isCurrentView],
  );

  const sendMessage = useCallback((content: string, options?: SendMessageOptions) =>
    dispatchSend(content, options), [dispatchSend]);

  const retryRejectedSend = useCallback(async (): Promise<boolean> => {
    if (!token || !chatId || !isCurrentView() || streamingRef.current || finalizingRef.current) return false;
    const queue = rejectedSendsRef.current.get(chatId);
    const rejected = queue?.[0];
    if (!rejected) return false;
    const attempt = sendAttemptRef.current + 1;
    await dispatchSend(rejected.content, rejected.options, rejected);
    return isCurrentView() && sendAttemptRef.current === attempt;
  }, [token, chatId, isCurrentView, dispatchSend]);

  const beginRegenerateUi = useCallback(() => {
    if (!isCurrentView()) return;
    const attempt = ++sendAttemptRef.current;
    pendingSendRef.current = null;
    regenerateUiActiveRef.current = true;
    const popped = popLastAssistantMessage(messagesRef.current);
    regenerateBackupRef.current = popped.backup;
    messagesRef.current = popped.messages;
    setMessages((prev) => {
      const latest = popLastAssistantMessage(prev);
      if (latest.backup) regenerateBackupRef.current = latest.backup;
      messagesRef.current = latest.messages;
      return latest.messages;
    });

    setStreaming(true);
    streamingRef.current = true;
    assistantBuffer.current = "";
    updateStreamingDraft({ content: "" });
    appendStreamingPlaceholder();
    return () => isCurrentView() && sendAttemptRef.current === attempt;
  }, [appendStreamingPlaceholder, updateStreamingDraft, isCurrentView]);

  const regenerateResponse = useCallback(
    async (model?: string | null, clientGeo?: ClientGeo | null) => {
      if (!token || !chatId || !isCurrentView()) return;
      if (stoppedStreamedIdRef.current) {
        const socket = wsRef.current;
        wsRef.current = null;
        connectingRef.current = null;
        socket?.close();
        stoppedStreamedIdRef.current = null;
      }

      if (!regenerateUiActiveRef.current) {
        beginRegenerateUi();
      }
      const attempt = ++sendAttemptRef.current;

      await ensureConnected();
      if (!isCurrentView() || sendAttemptRef.current !== attempt) return;
      if (preferSseRef.current || wsRef.current?.readyState !== WebSocket.OPEN) {
        await regenerateViaSse(model, clientGeo);
        return;
      }

      wsTurnRef.current = wsRef.current;
      wsAuthFallbackRef.current = {
        socket: wsRef.current,
        retry: () => regenerateViaSse(model, clientGeo),
      };
      wsRef.current.send(
        JSON.stringify({
          type: "regenerate",
          model: model ?? null,
          ...clientGeoWsFields(clientGeo),
        }),
      );
    },
    [token, chatId, ensureConnected, beginRegenerateUi, regenerateViaSse, isCurrentView],
  );

  const stopGeneration = useCallback(() => {
    if (!isCurrentView()) return;
    sendAttemptRef.current += 1;
    const pendingRetry = pendingSendRef.current;
    if (pendingRetry?.retryingRejected && !pendingRetry.dispatched) {
      setMessages((previous) => previous.filter((message) => message.id !== pendingRetry.messageId));
    }
    pendingSendRef.current = null;
    if (chatId) rejectedSendsRef.current.delete(chatId);
    setRejectedSend(null);
    wsAuthFallbackRef.current = null;
    regenerateUiActiveRef.current = false;
    sseAbortRef.current?.abort();
    sseAbortRef.current = null;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "cancel" }));
    }
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    finalizingRef.current = false;
    setSendingMessageId(null);
    const draft = streamingDraftRef.current;
    assistantBuffer.current = "";
    updateStreamingDraft(null);
    // The server keeps the previous answer until it commits a replacement.
    // A stop with no replacement tokens must therefore restore that answer.
    const backup = regenerateBackupRef.current;
    regenerateBackupRef.current = null;
    const stoppedId = `streamed-${Date.now()}`;
    setMessages((prev) => {
      const streamingMsg = prev.find((m) => m.id === "streaming");
      if (!streamingMsg) return prev;
      const content = draft?.content ?? streamingMsg.content;
      if (!content.trim()) {
        return restoreAssistantMessage(prev.filter((m) => m.id !== "streaming"), backup);
      }
      return prev.map((m) =>
        m.id === "streaming"
          ? {
              ...m,
              id: stoppedId,
              content,
              search_sources: draft?.search_sources ?? m.search_sources,
              generationStopped: true,
            }
          : m,
      );
    });
    // Track the committed bubble id so the server's late `done` reconciles
    // it (real message_id + final_content) instead of appending a duplicate.
    stoppedStreamedIdRef.current = stoppedId;
  }, [updateStreamingDraft, isCurrentView, chatId]);

  return {
    messages,
    setMessages,
    streaming,
    finalizing,
    sendingMessageId,
    sendMessage,
    rejectedSend,
    retryRejectedSend,
    beginRegenerateUi,
    cancelRegenerateUi: restoreRegenerateBackup,
    regenerateResponse,
    stopGeneration,
    connect,
  };
}
