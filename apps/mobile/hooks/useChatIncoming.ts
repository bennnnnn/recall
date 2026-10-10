import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import { AccessibilityInfo } from "react-native";

import type { Message } from "@/lib/api";
import { isSseAbortError, type ChatSsePayload } from "@/lib/chat/sse";
import { clearPendingChatTtft, markChatFirstToken } from "@/lib/chat/latency";
import { createStreamCueGate } from "@/lib/chat/streamFeedback";
import type { ClientGeo } from "@/lib/clientGeo";
import {
  applyRelatedPrompts,
  applyStreamEndModel,
  buildDoneMergeInput,
  mergeDoneIntoMessages,
  relatedPromptsFromEvent,
  shouldIgnoreStoppedStreamEvent,
} from "@/lib/chat/socketReduce";
import type { StreamingDraft } from "@/lib/streamingDraftStore";
import { restoreAssistantMessage } from "@/lib/chat/regenerateLogic";
import { replaceStreamingMessageWithPartial } from "@/lib/chat/partialStream";
import type { ChatWsFallbackSignal, ChatWsTransport } from "@/lib/chat/wsTransport";
import type { ComposerSendDraft } from "@/lib/chat/sendLogic";

export type SendMessageOptions = {
  skipUserBubble?: boolean;
  trackSendingMessageId?: string;
  attachmentIds?: string[];
  localImageUri?: string | null;
  localFileUri?: string | null;
  localFileName?: string | null;
  localFileContentType?: string | null;
  model?: string | null;
  clientGeo?: ClientGeo | null;
  /** Original composer data, retained only for definitely-unsaved recovery. */
  composerDraft?: ComposerSendDraft;
};

export type PendingSend = {
  content: string;
  options: SendMessageOptions;
  messageId: string | null;
  retryingRejected: boolean;
  dispatched: boolean;
};

export type RejectedSend = PendingSend & { reason: "send_rejected" | "attachment_rejected" };

type Translate = (key: string) => string;

type IncomingArgs = {
  t: Translate;
  chatId: string | null;
  isCurrentView: () => boolean;
  currentSocket: () => ChatWsTransport | null;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setStreaming: Dispatch<SetStateAction<boolean>>;
  setFinalizing: Dispatch<SetStateAction<boolean>>;
  setSendingMessageId: Dispatch<SetStateAction<string | null>>;
  updateStreamingDraft: (draft: StreamingDraft | null) => void;
  appendStreamingPlaceholder: () => void;
  queueUnsavedSend: (pending: PendingSend, reason: RejectedSend["reason"]) => void;
  restoreRegenerateBackup: () => void;
  clearStreamingBubble: () => void;
  reportError: (message: string, code?: string) => void;
  clearTodoSyncTimers: () => void;
  streamingRef: MutableRefObject<boolean>;
  finalizingRef: MutableRefObject<boolean>;
  streamCueRef: MutableRefObject<ReturnType<typeof createStreamCueGate>>;
  wsAuthFallbackRef: MutableRefObject<{
    transport: ChatWsTransport;
    retry: () => Promise<void>;
  } | null>;
  assistantBufferRef: MutableRefObject<string>;
  streamingDraftRef: MutableRefObject<StreamingDraft | null>;
  pendingSendRef: MutableRefObject<PendingSend | null>;
  stoppedStreamedIdRef: MutableRefObject<string | null>;
  regenerateUiActiveRef: MutableRefObject<boolean>;
  regenerateBackupRef: MutableRefObject<Message | null>;
  ttftTurnIdRef: MutableRefObject<string | null>;
  firstReplyRef: MutableRefObject<boolean>;
  onFirstReplyRef: MutableRefObject<(() => void) | undefined>;
  onTodosSyncRef: MutableRefObject<(() => void) | undefined>;
  todoSyncTimersRef: MutableRefObject<ReturnType<typeof setTimeout>[]>;
  viewingChatIdRef: MutableRefObject<string | null>;
  rejectedSendsRef: MutableRefObject<Map<string, RejectedSend[]>>;
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
      if (shouldIgnoreStoppedStreamEvent(payload.type, streamingRef.current)) {
        return;
      }
      if (payload.type === "start" || payload.type === "status" || payload.type === "token") {
        streamCueRef.current.activity();
      }
      if (payload.type === "start") {
        wsAuthFallbackRef.current = null;
        setSendingMessageId(null);
        setFinalizing(false);
        setStreaming(true);
        streamingRef.current = true;
        assistantBufferRef.current = "";
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
          content: assistantBufferRef.current,
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
        markChatFirstToken(ttftTurnId, payload.type);
        assistantBufferRef.current += payload.content ?? "";
        updateStreamingDraft({
          content: assistantBufferRef.current,
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
        regenerateBackupRef.current = null;
        ttftTurnIdRef.current = null;
        setSendingMessageId(null);
        const stoppedId = stoppedStreamedIdRef.current;
        stoppedStreamedIdRef.current = null;
        if (!stoppedId) {
          streamCueRef.current.complete();
          AccessibilityInfo.announceForAccessibility(t("chat.reply_ready"));
        }
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        finalizingRef.current = false;
        assistantBufferRef.current = "";
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

      if (payload.type === "related_prompts" && typeof payload.message_id === "string") {
        const prompts = relatedPromptsFromEvent(payload);
        const messageId = payload.message_id;
        if (prompts) {
          setMessages((prev) => applyRelatedPrompts(prev, messageId, prompts));
        }
      }

      if (payload.type === "error") {
        streamCueRef.current.error();
        // These codes explicitly guarantee this user turn was never saved.
        // A start/status event alone is not acceptance; answer events are.
        const pending = pendingSendRef.current;
        pendingSendRef.current = null;
        clearPendingChatTtft(ttftTurnId ?? pending?.messageId);
        ttftTurnIdRef.current = null;
        const reason = payload.code === "busy" ? "send_rejected"
          : payload.code === "attachment_rejected" ? "attachment_rejected" : null;
        const queuedUnsaved = Boolean(pending && reason);
        if (pending && reason) queueUnsavedSend(pending, reason);
        regenerateUiActiveRef.current = false;
        wsAuthFallbackRef.current = null;
        stoppedStreamedIdRef.current = null;
        setSendingMessageId(null);
        setStreaming(false);
        setFinalizing(false);
        streamingRef.current = false;
        finalizingRef.current = false;
        const draft = streamingDraftRef.current;
        const partial = (draft?.content ?? assistantBufferRef.current).trim();
        assistantBufferRef.current = "";
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
          queuedUnsaved
            ? rejectedSendsRef.current.get(viewingChatIdRef.current ?? "")?.[0]?.reason
            : typeof payload.code === "string" ? payload.code : undefined,
        );
      }
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
