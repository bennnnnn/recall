import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { chatWebSocketUrl, Message, SearchSource } from "@/lib/api";
import { streamChatMessageSse, streamChatRegenerateSse, isSseAbortError, shouldAbortPriorSse, type ChatSsePayload } from "@/lib/chatSse";
import { clientGeoWsFields, type ClientGeo } from "@/lib/clientGeo";
import { getDeviceTimezone } from "@/lib/deviceTimezone";
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
  const connectingRef = useRef<Promise<void> | null>(null);
  const preferSseRef = useRef(false);
  const sseAbortRef = useRef<AbortController | null>(null);
  const sseAbortChatIdRef = useRef<string | null>(null);
  const viewingChatIdRef = useRef(chatId);
  viewingChatIdRef.current = chatId;
  const assistantBuffer = useRef("");
  const streamingDraftRef = useRef<StreamingDraft | null>(null);
  const draftRafRef = useRef<number | null>(null);
  const streamingRef = useRef(false);
  const finalizingRef = useRef(false);
  /** Prior assistant reply kept until regenerate succeeds or is rolled back. */
  const regenerateBackupRef = useRef<Message | null>(null);
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
    const backup = regenerateBackupRef.current;
    regenerateBackupRef.current = null;
    clearStreamingBubble();
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    if (backup) {
      setMessages((prev) => restoreAssistantMessage(prev, backup));
    }
  }, [clearStreamingBubble]);

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
    return () => {
      if (draftRafRef.current != null) {
        cancelAnimationFrame(draftRafRef.current);
      }
      clearTodoSyncTimers();
      // Do not abort SSE on unmount — New chat / leave must drain like WS.
      wsRef.current?.close();
    };
  }, []);

  // Close and reset socket when chat changes. Do not abort SSE — Stop is the
  // only hard cancel. Leftover SSE events are ignored via viewingChatIdRef.
  useEffect(() => {
    wsRef.current?.close();
    wsRef.current = null;
    connectingRef.current = null;
    preferSseRef.current = false;
    assistantBuffer.current = "";
    firstReplyRef.current = false;
    regenerateBackupRef.current = null;
    stoppedStreamedIdRef.current = null;
    clearTodoSyncTimers();
    updateStreamingDraft(null);
    setStreaming(false);
    setFinalizing(false);
    setSendingMessageId(null);
  }, [chatId, updateStreamingDraft]);

  const handleChatPayload = useCallback(
    (payload: ChatSsePayload) => {
      if (shouldIgnoreStoppedStreamEvent(payload.type, streamingRef.current)) {
        return;
      }
      if (payload.type === "start") {
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
        assistantBuffer.current += payload.content ?? "";
        updateStreamingDraft({
          content: assistantBuffer.current,
          search_sources: streamingDraftRef.current?.search_sources,
          status: undefined,
          statusDetail: undefined,
        });
      }

      if (payload.type === "stream_end") {
        setFinalizing(true);
        if (typeof payload.resolved_model === "string" && payload.resolved_model) {
          setMessages((prev) => applyStreamEndModel(prev, payload.resolved_model));
        }
      }

      if (payload.type === "done") {
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
          typeof payload.code === "string" ? payload.code : undefined,
        );
      }
    },
    [
      appendStreamingPlaceholder,
      clearStreamingBubble,
      restoreRegenerateBackup,
      reportError,
      updateStreamingDraft,
      t,
    ],
  );

  const handleChatPayloadForChat = useCallback(
    (boundChatId: string | null, payload: ChatSsePayload) => {
      if (viewingChatIdRef.current !== boundChatId) return;
      handleChatPayload(payload);
    },
    [handleChatPayload],
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
    if (!token || !chatId) return Promise.resolve();
    if (preferSseRef.current) return Promise.resolve();
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
      // Track whether the server ever sent us a frame. A close with no
      // message means the connection never authenticated (expired token) or
      // never reached the chat loop — fall back to SSE, which refreshes the
      // access token on 401, instead of retrying WS with the same stale token.
      let receivedAnyMessage = false;

      const timer = setTimeout(() => {
        ws.close();
        preferSseRef.current = true;
        resolve();
      }, WS_CONNECT_TIMEOUT_MS);

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
        preferSseRef.current = true;
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        resolve();
      };

      ws.onclose = () => {
        clearTimeout(timer);
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        // No frame ever arrived → the socket never authenticated (likely an
        // expired access token rejected by the server). Use SSE next so the
        // 401-refresh path can heal the session instead of looping on WS.
        if (!receivedAnyMessage) {
          preferSseRef.current = true;
        }
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

      ws.onmessage = (event) => {
        receivedAnyMessage = true;
        const payload = parseChatWsPayload(String(event.data));
        if (!payload) return;
        handleChatPayloadForChat(chatId, payload);
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
    restoreRegenerateBackup,
    reportError,
    handleChatPayloadForChat,
    updateStreamingDraft,
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
          onEvent: (payload) => handleChatPayloadForChat(chatId, payload),
        });
      } catch (err) {
        if (isSseAbortError(err)) return;
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
          onEvent: (payload) => handleChatPayloadForChat(chatId, payload),
        });
      } catch (err) {
        if (isSseAbortError(err)) return;
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

  const sendMessage = useCallback(
    async (
      content: string,
      options?: {
        skipUserBubble?: boolean;
        trackSendingMessageId?: string;
        attachmentIds?: string[];
        localImageUri?: string | null;
        localFileUri?: string | null;
        localFileName?: string | null;
        localFileContentType?: string | null;
        model?: string | null;
        clientGeo?: ClientGeo | null;
      },
    ) => {
      if (!token || !chatId) return;

      let trackedId = options?.trackSendingMessageId ?? null;
      if (!options?.skipUserBubble) {
        trackedId = `local-${Date.now()}`;
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

      if (preferSseRef.current || wsRef.current?.readyState !== WebSocket.OPEN) {
        await sendViaSse(content, {
          attachmentIds: options?.attachmentIds,
          model: options?.model,
          clientGeo: options?.clientGeo,
        });
        return;
      }

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
    [token, chatId, ensureConnected, appendStreamingPlaceholder, updateStreamingDraft, sendViaSse],
  );

  const beginRegenerateUi = useCallback(() => {
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
  }, [appendStreamingPlaceholder, updateStreamingDraft]);

  const regenerateResponse = useCallback(
    async (model?: string | null, clientGeo?: ClientGeo | null) => {
      if (!token || !chatId) return;

      const uiReady = messagesRef.current.some((m) => m.id === "streaming");
      if (!uiReady) {
        beginRegenerateUi();
      }

      await ensureConnected();
      if (preferSseRef.current || wsRef.current?.readyState !== WebSocket.OPEN) {
        await regenerateViaSse(model, clientGeo);
        return;
      }

      wsRef.current.send(
        JSON.stringify({
          type: "regenerate",
          model: model ?? null,
          ...clientGeoWsFields(clientGeo),
        }),
      );
    },
    [token, chatId, ensureConnected, beginRegenerateUi, regenerateViaSse],
  );

  const stopGeneration = useCallback(() => {
    sseAbortRef.current?.abort();
    sseAbortRef.current = null;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "cancel" }));
    }
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    const draft = streamingDraftRef.current;
    assistantBuffer.current = "";
    updateStreamingDraft(null);
    // After a stop the partial reply is the source of truth (the backend
    // already deleted any prior assistant on regenerate and persists this
    // partial). Drop backups so a later `error` can't wrongly restore them.
    regenerateBackupRef.current = null;
    const stoppedId = `streamed-${Date.now()}`;
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
  }, [updateStreamingDraft]);

  return {
    messages,
    setMessages,
    streaming,
    finalizing,
    sendingMessageId,
    sendMessage,
    beginRegenerateUi,
    cancelRegenerateUi: restoreRegenerateBackup,
    regenerateResponse,
    stopGeneration,
    connect,
  };
}
