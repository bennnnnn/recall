import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Message } from "@/lib/api";
import type { ChatSsePayload } from "@/lib/chat/sse";
import { clearPendingChatTtft } from "@/lib/chat/latency";
import { createStreamCueGate } from "@/lib/chat/streamFeedback";
import { clientGeoWsFields, type ClientGeo } from "@/lib/clientGeo";
import { getSessionGeneration } from "@/lib/auth";
import { useChatTransport } from "@/hooks/useChatTransport";
import {
  useChatIncomingEvents,
  type PendingSend,
  type RejectedSend,
  type SendMessageOptions,
} from "@/hooks/useChatIncoming";
import {
  publishStreamingDraft,
  type StreamingDraft,
} from "@/lib/streamingDraftStore";
import {
  popLastAssistantMessage,
  restoreAssistantMessage,
} from "@/lib/chat/regenerateLogic";
import type { ChatWsFallbackSignal, ChatWsTransport } from "@/lib/chat/wsTransport";
import type { ComposerSendDraft } from "@/lib/chat/sendLogic";

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
  const wsAuthFallbackRef = useRef<{
    transport: ChatWsTransport;
    retry: () => Promise<void>;
  } | null>(null);
  const sendAttemptRef = useRef(0);
  const pendingSendRef = useRef<PendingSend | null>(null);
  // Only explicit pre-persistence rejections belong here. Keep them across
  // conversation switches and newer sends until the user retries or stops.
  const rejectedSendsRef = useRef(new Map<string, RejectedSend[]>());
  const [rejectedSend, setRejectedSend] = useState<RejectedSend | null>(null);
  const mountedRef = useRef(true);
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
  const streamCueRef = useRef(createStreamCueGate());
  /** Optimistic user-message id for the in-flight send's TTFT sample (WS). */
  const ttftTurnIdRef = useRef<string | null>(null);
  const payloadHandlerRef = useRef<
    (boundChatId: string | null, payload: ChatSsePayload, turnId?: string | null) => void
  >(() => {});
  const fallbackHandlerRef = useRef<
    (socket: ChatWsTransport, signal: ChatWsFallbackSignal) => void
  >(() => {});
  const sendFailureRef = useRef<(error: unknown, turnId: string | null) => void>(() => {});
  const regenerateFailureRef = useRef<() => void>(() => {});
  const chatTransport = useChatTransport({
    token,
    chatId,
    isCurrentView,
    ttftTurnId: () => ttftTurnIdRef.current,
    onPayload: (boundChatId, payload, turnId) => payloadHandlerRef.current(boundChatId, payload, turnId),
    onFallback: (socket, signal) => fallbackHandlerRef.current(socket, signal),
    onSendFailure: (error, turnId) => sendFailureRef.current(error, turnId),
    onRegenerateFailure: () => regenerateFailureRef.current(),
  });
  const {
    connect: connectTransport,
    sendViaSse,
    regenerateViaSse,
    currentSocket,
    dropSocket,
    detach,
    abortSse,
    cancelSocket,
  } = chatTransport;

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

  /** Server never saved this user turn — drop the optimistic bubble and keep Retry. */
  const queueUnsavedSend = useCallback((pending: PendingSend, reason: RejectedSend["reason"]) => {
    const boundChatId = viewingChatIdRef.current;
    if (!boundChatId) return;
    const rejected: RejectedSend = { ...pending, reason };
    const queue = rejectedSendsRef.current.get(boundChatId) ?? [];
    if (rejected.retryingRejected) queue.unshift(rejected);
    else queue.push(rejected);
    rejectedSendsRef.current.set(boundChatId, queue);
    setRejectedSend(queue[0]);
    if (rejected.messageId) {
      setMessages((previous) => previous.filter((message) =>
        message.id !== rejected.messageId || message.role !== "user"));
    }
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
      // The transport hook closes the socket. Do not abort SSE — New chat
      // must drain like a WebSocket disconnect.
    };
  }, [clearTodoSyncTimers, updateStreamingDraft]);

  // Close and reset socket when chat changes. Do not abort SSE — Stop is the
  // only hard cancel. Leftover SSE events are ignored via viewingChatIdRef.
  useEffect(() => {
    detach();
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
    assistantBuffer.current = "";
    firstReplyRef.current = false;
    regenerateBackupRef.current = null;
    stoppedStreamedIdRef.current = null;
    regenerateUiActiveRef.current = false;
    ttftTurnIdRef.current = null;
    clearPendingChatTtft();
    clearTodoSyncTimers();
    updateStreamingDraft(null);
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    finalizingRef.current = false;
    setSendingMessageId(null);
  }, [viewIdentity, chatId, sessionGeneration, updateStreamingDraft, clearTodoSyncTimers, detach]);

  const {
    handleChatPayloadForChat,
    handleWsFallback,
    handleSendFailure,
    handleRegenerateFailure,
  } = useChatIncomingEvents({
    t,
    chatId,
    isCurrentView,
    currentSocket,
    setMessages,
    setStreaming,
    setFinalizing,
    setSendingMessageId,
    updateStreamingDraft,
    appendStreamingPlaceholder,
    queueUnsavedSend,
    restoreRegenerateBackup,
    clearStreamingBubble,
    reportError,
    clearTodoSyncTimers,
    streamingRef,
    finalizingRef,
    streamCueRef,
    wsAuthFallbackRef,
    assistantBufferRef: assistantBuffer,
    streamingDraftRef,
    pendingSendRef,
    stoppedStreamedIdRef,
    regenerateUiActiveRef,
    regenerateBackupRef,
    ttftTurnIdRef,
    firstReplyRef,
    onFirstReplyRef,
    onTodosSyncRef,
    todoSyncTimersRef,
    viewingChatIdRef,
    rejectedSendsRef,
  });

  const ensureConnected = useCallback(async () => {
    try {
      await connectTransport();
    } catch {
      reportError(t("chat.error_unreachable"));
    }
  }, [connectTransport, reportError, t]);

  const dispatchSend = useCallback(
    async (
      content: string,
      options?: SendMessageOptions,
      rejectedRetry?: RejectedSend,
    ) => {
      if (!token || !chatId || !isCurrentView() || streamingRef.current || finalizingRef.current) return;
      streamCueRef.current.reset();
      const attempt = ++sendAttemptRef.current;
      // Stop may still have a final frame in flight. A fresh connection keeps
      // that old frame from finalizing the next turn's placeholder.
      if (stoppedStreamedIdRef.current) {
        dropSocket();
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
          composerDraft: options?.composerDraft ? {
            text: options.composerDraft.text,
            attachment: options.composerDraft.attachment ? { ...options.composerDraft.attachment } : null,
          } : undefined,
          clientGeo: options?.clientGeo ? { ...options.clientGeo } : options?.clientGeo,
        },
      };
      ttftTurnIdRef.current = trackedId;
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

      const transport = currentSocket();
      if (!transport?.isOpen() || transport.shouldUseSse()) {
        await sendViaSse(content, {
          attachmentIds: options?.attachmentIds,
          model: options?.model,
          clientGeo: options?.clientGeo,
          ttftTurnId: trackedId,
        });
        return;
      }

      wsAuthFallbackRef.current = {
        transport,
        retry: () => sendViaSse(content, {
          attachmentIds: options?.attachmentIds,
          model: options?.model,
          clientGeo: options?.clientGeo,
          ttftTurnId: trackedId,
        }),
      };
      transport.sendMessage({
        content,
        attachment_ids: options?.attachmentIds ?? [],
        model: options?.model ?? null,
        ...clientGeoWsFields(options?.clientGeo),
      });
    },
    [token, chatId, ensureConnected, appendStreamingPlaceholder, updateStreamingDraft, sendViaSse, isCurrentView, dropSocket, currentSocket],
  );

  const sendMessage = useCallback((content: string, options?: SendMessageOptions) =>
    dispatchSend(content, options), [dispatchSend]);

  const retryRejectedSend = useCallback(async (): Promise<boolean> => {
    if (!token || !chatId || !isCurrentView() || streamingRef.current || finalizingRef.current) return false;
    const queue = rejectedSendsRef.current.get(chatId);
    const rejected = queue?.[0];
    if (!rejected || rejected.reason !== "send_rejected") return false;
    const attempt = sendAttemptRef.current + 1;
    await dispatchSend(rejected.content, rejected.options, rejected);
    return isCurrentView() && sendAttemptRef.current === attempt;
  }, [token, chatId, isCurrentView, dispatchSend]);

  const restoreRejectedAttachmentDraft = useCallback((restore: (draft: ComposerSendDraft) => boolean): boolean => {
    if (!token || !chatId || !isCurrentView() || streamingRef.current || finalizingRef.current) return false;
    const queue = rejectedSendsRef.current.get(chatId);
    const rejected = queue?.[0];
    if (!rejected || rejected.reason !== "attachment_rejected") return false;
    const original = rejected.options.composerDraft ?? { text: rejected.content, attachment: null };
    const attachment = original.attachment ? { ...original.attachment } : null;
    // The server has rejected this reference. A local file can be uploaded
    // again when the user sends, or replaced in the restored composer.
    if (attachment) delete attachment.existingAttachmentId;
    if (!restore({ text: original.text, attachment })) return false;
    queue!.shift();
    if (queue!.length === 0) rejectedSendsRef.current.delete(chatId);
    setRejectedSend(queue![0] ?? null);
    return true;
  }, [token, chatId, isCurrentView]);

  const beginRegenerateUi = useCallback(() => {
    if (!isCurrentView()) return;
    const attempt = ++sendAttemptRef.current;
    pendingSendRef.current = null;
    ttftTurnIdRef.current = null;
    clearPendingChatTtft();
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
      streamCueRef.current.reset();
      if (stoppedStreamedIdRef.current) {
        dropSocket();
        stoppedStreamedIdRef.current = null;
      }

      if (!regenerateUiActiveRef.current) {
        beginRegenerateUi();
      }
      const attempt = ++sendAttemptRef.current;

      await ensureConnected();
      if (!isCurrentView() || sendAttemptRef.current !== attempt) return;
      const transport = currentSocket();
      if (!transport?.isOpen() || transport.shouldUseSse()) {
        await regenerateViaSse(model, clientGeo);
        return;
      }

      wsAuthFallbackRef.current = {
        transport,
        retry: () => regenerateViaSse(model, clientGeo),
      };
      transport.sendRegenerate({
        model: model ?? null,
        ...clientGeoWsFields(clientGeo),
      });
    },
    [token, chatId, ensureConnected, beginRegenerateUi, regenerateViaSse, isCurrentView, dropSocket, currentSocket],
  );

  const stopGeneration = useCallback(() => {
    if (!isCurrentView()) return;
    streamCueRef.current.stopped();
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
    clearPendingChatTtft(ttftTurnIdRef.current);
    ttftTurnIdRef.current = null;
    abortSse();
    cancelSocket();
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
  }, [updateStreamingDraft, isCurrentView, chatId, abortSse, cancelSocket]);

  payloadHandlerRef.current = handleChatPayloadForChat;
  fallbackHandlerRef.current = handleWsFallback;
  sendFailureRef.current = handleSendFailure;
  regenerateFailureRef.current = handleRegenerateFailure;

  return {
    messages,
    setMessages,
    streaming,
    finalizing,
    sendingMessageId,
    sendMessage,
    rejectedSend,
    retryRejectedSend,
    restoreRejectedAttachmentDraft,
    beginRegenerateUi,
    cancelRegenerateUi: restoreRegenerateBackup,
    regenerateResponse,
    stopGeneration,
    connect: connectTransport,
  };
}
