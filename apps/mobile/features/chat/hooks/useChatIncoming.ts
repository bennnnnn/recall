import { useCallback, type MutableRefObject } from "react";

import type { Message } from "@/lib/api";
import { isSseAbortError, type ChatSsePayload } from "@/features/chat/model/sse";
import { clearPendingChatTtft } from "@/features/chat/model/latency";
import { applyChatEvent, type ChatEventContext } from "@/features/chat/model/chatEvents";
import { restoreAssistantMessage } from "@/features/chat/model/regenerateLogic";
import { replaceStreamingMessageWithPartial } from "@/features/chat/model/partialStream";
import type { PendingSend } from "@/features/chat/model/sendLogic";
import {
  mergeReconciledPage,
  SSE_DROPPED_TURN_POLLS,
  type DroppedTurnResult,
} from "@/features/chat/model/turnReconcile";
import type { ChatWsFallbackSignal, ChatWsTransport } from "@/features/chat/model/wsTransport";
import { useDroppedTurnReconcile } from "@/features/chat/hooks/useDroppedTurnReconcile";

type IncomingArgs = ChatEventContext & {
  token: string | null;
  chatId: string | null;
  isCurrentView: () => boolean;
  currentSocket: () => ChatWsTransport | null;
  messagesRef: MutableRefObject<Message[]>;
  sendAttemptRef: MutableRefObject<number>;
};

/** Applies socket and SSE frames, plus the failures that follow a dropped turn. */
export function useChatIncomingEvents({
  t,
  token,
  chatId,
  isCurrentView,
  currentSocket,
  messagesRef,
  sendAttemptRef,
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

  const reconcileDroppedTurn = useDroppedTurnReconcile({
    token,
    chatId,
    isCurrentView,
    messagesRef,
    sendAttemptRef,
    streamingRef,
  });

  /** The dropped turn as the server saved it, in place of its streaming bubble. */
  const settleWithServerPage = useCallback((page: Message[]) => {
    clearPendingChatTtft(ttftTurnIdRef.current);
    ttftTurnIdRef.current = null;
    setSendingMessageId(null);
    setStreaming(false);
    setFinalizing(false);
    streamingRef.current = false;
    finalizingRef.current = false;
    assistantBufferRef.current = "";
    updateStreamingDraft(null);
    setMessages((prev) => mergeReconciledPage(prev, page));
    streamCueRef.current.complete();
    if (!firstReplyRef.current) {
      firstReplyRef.current = true;
      onFirstReplyRef.current?.();
    }
  }, [
    assistantBufferRef,
    finalizingRef,
    firstReplyRef,
    onFirstReplyRef,
    setFinalizing,
    setMessages,
    setSendingMessageId,
    setStreaming,
    streamCueRef,
    streamingRef,
    ttftTurnIdRef,
    updateStreamingDraft,
  ]);

  /** A send the server took (`start`, or a token shown): a drop is not a rejection. */
  const serverTookSend = useCallback(
    (pending: PendingSend | null) =>
      !regenerateBackupRef.current &&
      (Boolean(pending?.accepted) || assistantBufferRef.current.trim().length > 0),
    [assistantBufferRef, regenerateBackupRef],
  );

  /** Keep the bubble up and reload the chat until the reply lands; `settleLost`
   * runs only when it does not, told whether the message is in the chat. */
  const followTakenSend = useCallback(
    (settleLost: (messageSaved: boolean) => void, polls?: number) => {
      reconcileDroppedTurn((result: DroppedTurnResult) => {
        if (result.state === "answered" && result.page) {
          settleWithServerPage(result.page);
          return;
        }
        // Replay only what a reload showed is not in the chat.
        settleLost(result.state !== "missing");
      }, polls);
    },
    [reconcileDroppedTurn, settleWithServerPage],
  );

  const settleDroppedSocketTurn = useCallback((pending: PendingSend | null, messageSaved: boolean) => {
    if (!streamingRef.current && !finalizingRef.current) return;
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
      if (!hadContent) return restoreAssistantMessage(prev, failedRegenerateBackup);
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
      if (pending && !messageSaved) {
        queueUnsavedSend(pending, "send_rejected");
        reportError(t("chat.error_unreachable"), "send_rejected");
      } else {
        reportError(t("chat.error_connection_lost"));
      }
    }
  }, [
    assistantBufferRef,
    finalizingRef,
    queueUnsavedSend,
    regenerateBackupRef,
    reportError,
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
  ]);

  /**
   * A reply past `stream_end` whose `done` never came (its connection gone quiet):
   * the server has the turn, so reload the chat until the saved reply lands, as
   * after a drop. A regenerated reply has no new message to find there; it settles
   * as a dropped one at once.
   */
  const reconcileUnconfirmedReply = useCallback(() => {
    if (!finalizingRef.current) return;
    if (regenerateBackupRef.current) {
      settleDroppedSocketTurn(null, true);
      return;
    }
    followTakenSend((messageSaved) => settleDroppedSocketTurn(null, messageSaved));
  }, [finalizingRef, regenerateBackupRef, settleDroppedSocketTurn, followTakenSend]);

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

    if (signal.reason === "closed_unread" && signal.duringTurn) {
      // The server closed (idle, or over the socket cap) without reading this
      // send. Until `start` the fallback is still armed: replay it, unseen.
      const fallback = wsAuthFallbackRef.current;
      if (fallback?.transport === transport) {
        wsAuthFallbackRef.current = null;
        void fallback.retry();
        return;
      }
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
    if (serverTookSend(pending) && (streamingRef.current || finalizingRef.current)) {
      // The server finishes a turn whose socket dropped (and saves it on a deploy).
      followTakenSend((messageSaved) => settleDroppedSocketTurn(pending, messageSaved));
      return;
    }
    settleDroppedSocketTurn(pending, false);
  }, [
    assistantBufferRef,
    chatId,
    currentSocket,
    finalizingRef,
    followTakenSend,
    handleChatPayloadForChat,
    isCurrentView,
    pendingSendRef,
    reportError,
    restoreRegenerateBackup,
    serverTookSend,
    setSendingMessageId,
    settleDroppedSocketTurn,
    streamCueRef,
    streamingRef,
    t,
    ttftTurnIdRef,
    wsAuthFallbackRef,
  ]);

  const settleFailedSend = useCallback((
    err: unknown,
    ttftTurnId: string | null,
    pending: PendingSend | null,
    messageSaved: boolean,
  ) => {
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
      if (pending && !messageSaved && !isSseAbortError(err)) {
        queueUnsavedSend(pending, "send_rejected");
        reportError(t("chat.error_unreachable"), "send_rejected");
        return;
      }
    }
    reportError(t("chat.error_unreachable"));
  }, [
    clearStreamingBubble,
    finalizingRef,
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

  const handleSendFailure = useCallback((err: unknown, ttftTurnId: string | null) => {
    const pending = pendingSendRef.current;
    pendingSendRef.current = null;
    if (!isSseAbortError(err) && serverTookSend(pending) && streamingRef.current) {
      // A dropped SSE stream stops its turn on the server, which saves at once.
      followTakenSend(
        (messageSaved) => settleFailedSend(err, ttftTurnId, pending, messageSaved),
        SSE_DROPPED_TURN_POLLS,
      );
      return;
    }
    settleFailedSend(err, ttftTurnId, pending, false);
  }, [followTakenSend, pendingSendRef, serverTookSend, settleFailedSend, streamingRef]);

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
    reconcileUnconfirmedReply,
  };
}
