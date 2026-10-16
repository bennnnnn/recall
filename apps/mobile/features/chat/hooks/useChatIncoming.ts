import { useCallback } from "react";

import { isSseAbortError, type ChatSsePayload } from "@/features/chat/model/sse";
import { clearPendingChatTtft } from "@/features/chat/model/latency";
import { applyChatEvent, type ChatEventContext } from "@/features/chat/model/chatEvents";
import { restoreAssistantMessage } from "@/features/chat/model/regenerateLogic";
import { replaceStreamingMessageWithPartial } from "@/features/chat/model/partialStream";
import type { ChatWsFallbackSignal, ChatWsTransport } from "@/features/chat/model/wsTransport";

type IncomingArgs = ChatEventContext & {
  chatId: string | null;
  isCurrentView: () => boolean;
  currentSocket: () => ChatWsTransport | null;
};

/** Applies socket and SSE frames, plus the failures that follow a dropped turn. */
export function useChatIncomingEvents({
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
  assistantBufferRef,
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
}: IncomingArgs) {
  const handleChatPayload = useCallback(
    (payload: ChatSsePayload, ttftTurnId?: string | null) => {
      applyChatEvent(payload, {
        t, setMessages, setStreaming, setFinalizing, setSendingMessageId, updateStreamingDraft,
        appendStreamingPlaceholder, queueUnsavedSend, restoreRegenerateBackup, clearStreamingBubble,
        reportError, clearTodoSyncTimers, streamingRef, finalizingRef, streamCueRef, wsAuthFallbackRef,
        assistantBufferRef, streamingDraftRef, pendingSendRef, stoppedStreamedIdRef, regenerateUiActiveRef,
        regenerateBackupRef, ttftTurnIdRef, firstReplyRef, onFirstReplyRef, onTodosSyncRef,
        todoSyncTimersRef, viewingChatIdRef, rejectedSendsRef,
      }, ttftTurnId);
    },
    [
      appendStreamingPlaceholder,
      assistantBufferRef,
      clearStreamingBubble,
      clearTodoSyncTimers,
      finalizingRef,
      firstReplyRef,
      onFirstReplyRef,
      onTodosSyncRef,
      pendingSendRef,
      queueUnsavedSend,
      regenerateBackupRef,
      regenerateUiActiveRef,
      rejectedSendsRef,
      reportError,
      restoreRegenerateBackup,
      setFinalizing,
      setMessages,
      setSendingMessageId,
      setStreaming,
      stoppedStreamedIdRef,
      streamCueRef,
      streamingDraftRef,
      streamingRef,
      t,
      todoSyncTimersRef,
      ttftTurnIdRef,
      updateStreamingDraft,
      viewingChatIdRef,
      wsAuthFallbackRef,
    ],
  );

  const handleChatPayloadForChat = useCallback(
    (boundChatId: string | null, payload: ChatSsePayload, ttftTurnId?: string | null) => {
      if (!isCurrentView() || viewingChatIdRef.current !== boundChatId) return;
      handleChatPayload(payload, ttftTurnId);
    },
    [handleChatPayload, isCurrentView, viewingChatIdRef],
  );

  const preservePartialStream = useCallback((): boolean => {
    const draft = streamingDraftRef.current;
    const partial = (draft?.content ?? assistantBufferRef.current).trim();
    assistantBufferRef.current = "";
    if (!partial) return false;

    const keptId = `streamed-${Date.now()}`;
    updateStreamingDraft(null);
    setMessages((prev) =>
      replaceStreamingMessageWithPartial(prev, partial, draft, keptId),
    );
    return true;
  }, [assistantBufferRef, setMessages, streamingDraftRef, updateStreamingDraft]);

  const handleWsFallback = useCallback((
    transport: ChatWsTransport,
    signal: ChatWsFallbackSignal,
  ) => {
    if (!isCurrentView() || currentSocket() !== transport) return;
    if (signal.reason === "connect_timeout") return;

    if (signal.reason === "unauthorized") {
      // The server rejects auth before accepting the turn. Only this explicit
      // rejection is safe to replay through REST's token refresh.
      const fallback = wsAuthFallbackRef.current;
      if (!fallback && signal.duringTurn) {
        handleChatPayloadForChat(chatId, signal.payload, ttftTurnIdRef.current);
        return;
      }
      wsAuthFallbackRef.current = null;
      if (fallback?.transport === transport) void fallback.retry();
      return;
    }

    if (signal.reason === "first_event_timeout") {
      // No event does not prove the server missed the request. Retain the user
      // bubble and never replay this uncertain turn.
      wsAuthFallbackRef.current = null;
      pendingSendRef.current = null;
      clearPendingChatTtft(ttftTurnIdRef.current);
      ttftTurnIdRef.current = null;
      setSendingMessageId(null);
      assistantBufferRef.current = "";
      restoreRegenerateBackup();
      reportError(t("chat.error_unreachable"));
      streamCueRef.current.error();
      return;
    }

    if (!signal.duringTurn) return;
    const pending = pendingSendRef.current;
    pendingSendRef.current = null;
    if (streamingRef.current || finalizingRef.current) {
      setStreaming(false);
      setFinalizing(false);
      streamingRef.current = false;
      finalizingRef.current = false;
      const hadContent = assistantBufferRef.current.trim().length > 0;
      const draft = streamingDraftRef.current;
      const failedRegenerateBackup = regenerateBackupRef.current;
      regenerateBackupRef.current = null;
      assistantBufferRef.current = "";
      updateStreamingDraft(null);
      setSendingMessageId(null);
      if (!hadContent) {
        clearPendingChatTtft(ttftTurnIdRef.current ?? pending?.messageId);
        ttftTurnIdRef.current = null;
      }
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
      streamCueRef.current.error();
      if (hadContent) {
        reportError(t("chat.error_connection_lost"));
      } else if (!failedRegenerateBackup) {
        if (pending) {
          queueUnsavedSend(pending, "send_rejected");
          reportError(t("chat.error_unreachable"), "send_rejected");
        } else {
          reportError(t("chat.error_connection_lost"));
        }
      }
    }
  }, [
    assistantBufferRef,
    chatId,
    currentSocket,
    finalizingRef,
    handleChatPayloadForChat,
    isCurrentView,
    pendingSendRef,
    queueUnsavedSend,
    regenerateBackupRef,
    reportError,
    restoreRegenerateBackup,
    setFinalizing,
    setMessages,
    setSendingMessageId,
    setStreaming,
    streamCueRef,
    streamingDraftRef,
    streamingRef,
    t,
    ttftTurnIdRef,
    updateStreamingDraft,
    wsAuthFallbackRef,
  ]);

  const handleSendFailure = useCallback((err: unknown, ttftTurnId: string | null) => {
    const pending = pendingSendRef.current;
    pendingSendRef.current = null;
    clearPendingChatTtft(ttftTurnId ?? pending?.messageId);
    ttftTurnIdRef.current = null;
    setSendingMessageId(null);
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    finalizingRef.current = false;
    if (!preservePartialStream()) {
      clearStreamingBubble();
      // A private HTTP timeout may happen after the server received the
      // turn. Only caller cancellation is silent; keep uncertain delivery
      // out of the definitely-unsaved retry queue.
      if (pending && !isSseAbortError(err)) {
        queueUnsavedSend(pending, "send_rejected");
        reportError(t("chat.error_unreachable"), "send_rejected");
        return;
      }
    }
    reportError(t("chat.error_unreachable"));
  }, [
    clearStreamingBubble,
    finalizingRef,
    pendingSendRef,
    preservePartialStream,
    queueUnsavedSend,
    reportError,
    setFinalizing,
    setSendingMessageId,
    setStreaming,
    streamingRef,
    t,
    ttftTurnIdRef,
  ]);

  const handleRegenerateFailure = useCallback(() => {
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
  }, [
    finalizingRef,
    preservePartialStream,
    regenerateBackupRef,
    reportError,
    restoreRegenerateBackup,
    setFinalizing,
    setStreaming,
    streamingRef,
    t,
  ]);

  return {
    handleChatPayloadForChat,
    handleWsFallback,
    handleSendFailure,
    handleRegenerateFailure,
  };
}
