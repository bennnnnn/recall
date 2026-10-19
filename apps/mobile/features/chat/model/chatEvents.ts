import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { AccessibilityInfo } from "react-native";

import type { Message } from "@/lib/api";
import type { StreamingDraft } from "@/lib/streamingDraftStore";
import { clearPendingChatTtft, markChatFirstToken } from "@/features/chat/model/latency";
import type { PendingSend, RejectedSend } from "@/features/chat/model/sendLogic";
import type { ChatSsePayload } from "@/features/chat/model/sse";
import type { createStreamCueGate } from "@/features/chat/model/streamFeedback";
import type { ChatWsTransport } from "@/features/chat/model/wsTransport";
import {
  beginTurnOutcome,
  completionFromDone,
  noteTurnActivity,
  reportTurnOutcome,
} from "@/features/chat/model/turnOutcome";
import {
  applyRelatedPrompts,
  applyStreamEndModel,
  buildDoneMergeInput,
  mergeDoneIntoMessages,
  relatedPromptsFromEvent,
  shouldIgnoreStoppedStreamEvent,
} from "@/features/chat/model/socketReduce";

/** What a chat event may read and change: useChat's state setters, refs and callbacks. */
export type ChatEventContext = {
  t: (key: string) => string;
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

type ChatEventType =
  | "start"
  | "status"
  | "token"
  | "reasoning"
  | "stream_end"
  | "done"
  | "related_prompts"
  | "error";

type ChatEventHandler = (
  payload: ChatSsePayload,
  ctx: ChatEventContext,
  ttftTurnId?: string | null,
) => void;

/** Background Schedule extraction can finish after `done`, so the to-do list refreshes again. */
const TODO_RESYNC_DELAYS_MS = [2_500, 7_000] as const;

const done: ChatEventHandler = (payload, ctx) => {
  ctx.pendingSendRef.current = null;
  ctx.regenerateUiActiveRef.current = false;
  ctx.wsAuthFallbackRef.current = null;
  ctx.regenerateBackupRef.current = null;
  ctx.ttftTurnIdRef.current = null;
  ctx.setSendingMessageId(null);
  const stoppedId = ctx.stoppedStreamedIdRef.current;
  ctx.stoppedStreamedIdRef.current = null;
  if (!stoppedId) {
    ctx.streamCueRef.current.complete();
    AccessibilityInfo.announceForAccessibility(ctx.t("chat.reply_ready"));
    // A stopped turn was reported when the user tapped Stop.
    reportTurnOutcome(completionFromDone(payload.completion));
  }
  ctx.setStreaming(false);
  ctx.setFinalizing(false);
  ctx.streamingRef.current = false;
  ctx.finalizingRef.current = false;
  ctx.assistantBufferRef.current = "";
  const draft = ctx.streamingDraftRef.current;
  ctx.updateStreamingDraft(null);
  ctx.setMessages((prev) =>
    mergeDoneIntoMessages(prev, buildDoneMergeInput(payload, draft, undefined, stoppedId)),
  );
  if (!ctx.firstReplyRef.current) {
    ctx.firstReplyRef.current = true;
    ctx.onFirstReplyRef.current?.();
  }
  if (payload.todos_changed) {
    ctx.onTodosSyncRef.current?.();
    // Tracked so they're cancelled on chat switch / unmount (no firing on the
    // wrong chat after navigating away).
    ctx.clearTodoSyncTimers();
    for (const delay of TODO_RESYNC_DELAYS_MS) {
      ctx.todoSyncTimersRef.current.push(setTimeout(() => ctx.onTodosSyncRef.current?.(), delay));
    }
  }
};

/** Errors whose own action (upgrade, change model) stands in for Retry. */
const OWN_RECOVERY_CODES = new Set(["quota_exceeded", "model_unavailable"]);

/** Why a failed send can be offered again: the server says its message is not in the chat. */
function unsavedReason(payload: ChatSsePayload): RejectedSend["reason"] | null {
  if (payload.code === "attachment_rejected") return "attachment_rejected";
  if (payload.code === "busy") return "send_rejected";
  const ownRecovery = OWN_RECOVERY_CODES.has(payload.code ?? "");
  return payload.user_message_saved === false && !ownRecovery ? "send_rejected" : null;
}

const error: ChatEventHandler = (payload, ctx, ttftTurnId) => {
  ctx.streamCueRef.current.error();
  reportTurnOutcome("error", typeof payload.code === "string" ? payload.code : undefined);
  // Only an unsaved message is offered as Retry (resend); a saved one keeps
  // Regenerate. Servers that predate `user_message_saved` say so by code.
  const pending = ctx.pendingSendRef.current;
  ctx.pendingSendRef.current = null;
  clearPendingChatTtft(ttftTurnId ?? pending?.messageId);
  ctx.ttftTurnIdRef.current = null;
  const reason = unsavedReason(payload);
  const queuedUnsaved = Boolean(pending && reason);
  if (pending && reason) ctx.queueUnsavedSend(pending, reason);
  ctx.regenerateUiActiveRef.current = false;
  ctx.wsAuthFallbackRef.current = null;
  ctx.stoppedStreamedIdRef.current = null;
  ctx.setSendingMessageId(null);
  ctx.setStreaming(false);
  ctx.setFinalizing(false);
  ctx.streamingRef.current = false;
  ctx.finalizingRef.current = false;
  const draft = ctx.streamingDraftRef.current;
  const partial = (draft?.content ?? ctx.assistantBufferRef.current).trim();
  ctx.assistantBufferRef.current = "";
  if (ctx.regenerateBackupRef.current) {
    ctx.restoreRegenerateBackup();
  } else if (partial) {
    // Keep what the user already saw (same idea as stop / disconnect).
    const keptId = `streamed-${Date.now()}`;
    ctx.updateStreamingDraft(null);
    ctx.setMessages((prev) => {
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
    ctx.stoppedStreamedIdRef.current = keptId;
  } else {
    ctx.clearStreamingBubble();
  }
  ctx.reportError(
    payload.message ?? ctx.t("chat.error_generic"),
    queuedUnsaved
      ? ctx.rejectedSendsRef.current.get(ctx.viewingChatIdRef.current ?? "")?.[0]?.reason
      : typeof payload.code === "string" ? payload.code : undefined,
  );
};

/** One handler per event the chat socket or SSE stream sends. */
export const CHAT_EVENT_HANDLERS: Record<ChatEventType, ChatEventHandler> = {
  start: (_payload, ctx) => {
    ctx.streamCueRef.current.activity();
    beginTurnOutcome();
    // The server took the turn and finishes it even if the connection drops:
    // from here a drop is reconciled with the chat, never sent a second time.
    if (ctx.pendingSendRef.current) ctx.pendingSendRef.current.accepted = true;
    ctx.wsAuthFallbackRef.current = null;
    ctx.setSendingMessageId(null);
    ctx.setFinalizing(false);
    ctx.setStreaming(true);
    ctx.streamingRef.current = true;
    ctx.assistantBufferRef.current = "";
    // Keep the instant local status (set at send time) instead of
    // blanking the label until the server's first status event.
    ctx.updateStreamingDraft({
      content: "",
      status: ctx.streamingDraftRef.current?.status,
      statusDetail: ctx.streamingDraftRef.current?.statusDetail,
    });
    ctx.appendStreamingPlaceholder();
  },
  status: (payload, ctx) => {
    ctx.streamCueRef.current.activity();
    if (typeof payload.phase !== "string") return;
    noteTurnActivity(payload.phase);
    ctx.updateStreamingDraft({
      content: ctx.assistantBufferRef.current,
      search_sources: ctx.streamingDraftRef.current?.search_sources,
      status: payload.phase,
      statusDetail: typeof payload.detail === "string" && payload.detail ? payload.detail : undefined,
    });
  },
  token: (payload, ctx, ttftTurnId) => {
    ctx.streamCueRef.current.activity();
    ctx.pendingSendRef.current = null;
    markChatFirstToken(ttftTurnId, payload.type);
    ctx.assistantBufferRef.current += payload.content ?? "";
    ctx.updateStreamingDraft({
      content: ctx.assistantBufferRef.current,
      search_sources: ctx.streamingDraftRef.current?.search_sources,
      status: undefined,
      statusDetail: undefined,
    });
  },
  // CoT is not the answer; status/waiting already covers "the model is working".
  reasoning: () => {},
  stream_end: (payload, ctx) => {
    ctx.pendingSendRef.current = null;
    ctx.setFinalizing(true);
    if (typeof payload.resolved_model === "string" && payload.resolved_model) {
      ctx.setMessages((prev) => applyStreamEndModel(prev, payload.resolved_model));
    }
  },
  done,
  related_prompts: (payload, ctx) => {
    if (typeof payload.message_id !== "string") return;
    const prompts = relatedPromptsFromEvent(payload);
    const messageId = payload.message_id;
    if (prompts) ctx.setMessages((prev) => applyRelatedPrompts(prev, messageId, prompts));
  },
  error,
};

function isChatEventType(type: string): type is ChatEventType {
  return Object.hasOwn(CHAT_EVENT_HANDLERS, type);
}

/** Applies one frame; late deltas after Stop and unknown types change nothing. */
export function applyChatEvent(
  payload: ChatSsePayload,
  ctx: ChatEventContext,
  ttftTurnId?: string | null,
): void {
  if (shouldIgnoreStoppedStreamEvent(payload.type, ctx.streamingRef.current)) return;
  if (isChatEventType(payload.type)) CHAT_EVENT_HANDLERS[payload.type](payload, ctx, ttftTurnId);
}
