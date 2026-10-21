import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Keyboard } from "react-native";
import { useRouter } from "expo-router";

import { useComposerDraftApi } from "@/contexts/ComposerDraftContext";
import { useActionFeedbackOptional } from "@/contexts/ActionFeedbackContext";

import type { useDraftChat } from "@/features/chat/hooks/useDraftChat";
import type { useChatScroll } from "@/features/chat/hooks/useChatScroll";
import { getSessionGeneration } from "@/lib/auth";
import type { Message } from "@/lib/api";
import { notifyWarning, tap } from "@/lib/haptics";
import { notifyOfflineSendBlocked } from "@/lib/offlineSendFeedback";
import {
  buildOptimisticUserMessage,
  buildPendingSendAfterCreate,
  type ComposerSendDraft,
  type SendMessageOptions,
} from "@/features/chat/model/sendLogic";
import { canSend } from "@/features/chat/model/sendGuards";
import { useComposerAttachmentSheet } from "@/features/chat/hooks/useComposerAttachmentSheet";
import { useChatSendRoute, type PaintedSend } from "@/features/chat/hooks/useChatSendRoute";
import { useEnsureChatId } from "@/features/chat/hooks/useEnsureChatId";
import { useMathScanSend } from "@/features/chat/hooks/useMathScanSend";
import { useRestoreFailedSend, type SendTurn } from "@/features/chat/hooks/useRestoreFailedSend";
import { useSendAttachment } from "@/features/chat/hooks/useSendAttachment";
import type { SendTurnStart } from "@/features/chat/hooks/useTurnStart";
import { composerThreadKey } from "@/features/chat/model/composerThreadDraft";
import type { ImageGenSubmit } from "@/features/images/hooks/useImageGeneration";
import { queryNeedsClientGeo } from "@/lib/resolveClientGeoForQuery";
import { discardDraftAttachment, type PendingAttachment } from "@/features/attachments/model/attachments";
import {
  subscribeComposerAttachmentQueue,
  takeQueuedComposerAttachment,
} from "@/features/attachments/model/pendingComposerAttachment";

type Router = ReturnType<typeof useRouter>;
type DraftChat = ReturnType<typeof useDraftChat>;
type ChatScroll = ReturnType<typeof useChatScroll>;
type ChatSendPhase =
  | "idle"
  | "locating"
  | "preparing"
  | "uploading"
  | "creating";

type SendMessageFn = (text: string, opts?: SendMessageOptions) => void;

/** A send waiting for its new chat's id; dropped if the view moves on first. */
type PendingChatSend = ReturnType<typeof buildPendingSendAfterCreate> & {
  chatId: string;
  session: number;
  originViewVersion: number;
};

type Options = {
  token: string | null;
  chatId: string | null;
  chatLoading?: boolean;
  /** Route `chatId` — composer drafts key off this, not the lagging loaded id. */
  routeChatId?: string;
  setChatId: React.Dispatch<React.SetStateAction<string | null>>;
  setChatTitle: React.Dispatch<React.SetStateAction<string | null>>;
  router: Router;
  draft: DraftChat;
  scroll: ChatScroll;
  streaming: boolean;
  sendMessage: SendMessageFn;
  /** Typing dots that go up with the bubble, before the turn is sent. */
  sendStart: SendTurnStart;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  /** Current transcript — a short follow-up after a picture is worth asking the server about. */
  messages: Message[];
  selectedModel: string;
  updateUser: (patch: Partial<import("@/lib/api").User>) => Promise<void>;
  t: (key: string, options?: Record<string, unknown>) => string;
  onStreamBusy?: () => void;
  /** Soft offline cue (toast) — prefer over a blocking Alert; draft stays in the composer. */
  onOfflineBlocked?: () => void;
  isOffline: boolean;
  /** Run image generation for detected image-intent text (no confirmation sheet). */
  onGenerateImage?: (request: ImageGenSubmit) => void;
  imageGenerating?: boolean;
};

export function useChatSend({
  token,
  chatId,
  chatLoading = false,
  routeChatId,
  setChatId,
  setChatTitle,
  router,
  draft,
  scroll,
  streaming,
  sendMessage,
  sendStart,
  setMessages,
  messages,
  selectedModel,
  updateUser,
  t,
  onStreamBusy,
  onOfflineBlocked,
  isOffline,
  onGenerateImage,
  imageGenerating = false,
}: Options) {
  const { creatingRef, discardEmptyChat } = draft;
  const { newMessageCountRef } = scroll;

  const {
    setInput,
    inputRef,
    switchThread,
    adoptComposerThread,
    stashFailedDraftForThread,
    resetForNewSession,
    getThreadKey,
  } = useComposerDraftApi();
  const feedback = useActionFeedbackOptional();
  const {
    pendingAttachment, pendingAttachmentRef, setPendingAttachment, replacePendingAttachment,
    switchAttachmentThread, stashAttachmentForThread, resetAttachmentDrafts,
  } = useSendAttachment(token);
  const ensureChatId = useEnsureChatId({ chatId, selectedModel, draft, setChatId, setChatTitle, router });
  const [sendPhase, setSendPhase] = useState<ChatSendPhase>("idle");
  const [pendingOutboundId, setPendingOutboundId] = useState<string | null>(null);
  const [pendingSend, setPendingSend] = useState<PendingChatSend | null>(null);

  const sendInFlightRef = useRef(false);
  const composerThread = composerThreadKey(routeChatId);
  const session = getSessionGeneration();
  const viewRef = useRef({ session, composerThread, version: 0 });
  if (viewRef.current.session !== session || viewRef.current.composerThread !== composerThread) {
    viewRef.current = { session, composerThread, version: viewRef.current.version + 1 };
  }
  useEffect(() => () => {
    viewRef.current.version += 1;
  }, []);
  const {
    attachSheetOpen,
    setAttachSheetOpen,
    mathScannerOpen,
    setMathScannerOpen,
    attachPicking,
    attachPickInFlightRef,
    handlePickAttachment,
    handleAttachmentSheetSelect,
  } = useComposerAttachmentSheet({
    token,
    streaming,
    session,
    viewRef,
    sendInFlightRef,
    replacePendingAttachment,
    feedback,
    t,
  });

  const prevComposerThreadRef = useRef(composerThread);
  const prevSessionRef = useRef(session);
  useLayoutEffect(() => {
    const fromKey = getThreadKey();
    const accountChanged = prevSessionRef.current !== session;
    prevSessionRef.current = session;
    // Wipe before switchThread: the shared "new" key no-ops and would keep the
    // previous account's unsent text if we only switched.
    if (accountChanged) {
      resetForNewSession();
      resetAttachmentDrafts();
    }
    switchThread(composerThread);
    if (!accountChanged && prevComposerThreadRef.current === composerThread) return;
    prevComposerThreadRef.current = composerThread;
    sendInFlightRef.current = false;
    setSendPhase("idle");
    setPendingOutboundId(null);
    if (!accountChanged && fromKey === composerThread) return;
    if (!accountChanged) switchAttachmentThread(fromKey, composerThread);
    setAttachSheetOpen(false);
    setMathScannerOpen(false);
  }, [
    composerThread, session, switchThread, getThreadKey, switchAttachmentThread, resetForNewSession,
    resetAttachmentDrafts, setAttachSheetOpen, setMathScannerOpen,
  ]);
  useEffect(() => {
    const applyQueued = () => {
      if (!token || session !== getSessionGeneration()) return;
      const next = takeQueuedComposerAttachment(composerThread);
      if (next) replacePendingAttachment(next);
    };
    applyQueued();
    return subscribeComposerAttachmentQueue(applyQueued);
  }, [composerThread, token, session, replacePendingAttachment]);
  useEffect(() => {
    if (
      pendingSend &&
      (session !== pendingSend.session ||
        (routeChatId != null
          ? routeChatId !== pendingSend.chatId
          : viewRef.current.version !== pendingSend.originViewVersion))
    ) {
      if (session === pendingSend.session) {
        stashFailedDraftForThread(pendingSend.chatId, pendingSend.text);
        stashAttachmentForThread(pendingSend.chatId, getThreadKey(), pendingSend.composerDraft.attachment);
      } else discardDraftAttachment(null, pendingSend.composerDraft.attachment);
      setPendingSend(null);
      setPendingOutboundId(null);
      sendInFlightRef.current = false;
      setSendPhase("idle");
      return;
    }
    if (chatId && pendingSend && chatId === pendingSend.chatId) {
      const {
        text,
        skipUserBubble,
        trackSendingMessageId,
        attachmentIds,
        localImageUri,
        localFileUri,
        localFileName,
        localFileContentType,
        clientGeo,
        composerDraft,
        model,
      } = pendingSend;
      setPendingSend(null);
      sendMessage(text, {
        skipUserBubble,
        trackSendingMessageId,
        attachmentIds,
        localImageUri,
        localFileUri,
        localFileName,
        localFileContentType,
        model,
        clientGeo,
        composerDraft,
      });
      setPendingOutboundId(null);
      sendInFlightRef.current = false;
      setSendPhase("idle");
    }
  }, [chatId, routeChatId, session, pendingSend, sendMessage, stashFailedDraftForThread, stashAttachmentForThread, getThreadKey]);

  /** Clears the composer and paints the user's bubble, with typing dots when they can go up. */
  const paintUserTurn = useCallback((text: string, attached: PendingAttachment | null, tappedAt: number) => {
    // Clear the composer immediately so the next draft can be typed.
    // Keep Send/Attach busy until the turn is accepted — an idle button
    // with sendInFlightRef set looked finished and ate the next tap.
    setInput("");
    setPendingAttachment(null);
    Keyboard.dismiss();

    const optimisticId = `local-${tappedAt}`;
    const createdAt = new Date(tappedAt).toISOString();
    setPendingOutboundId(optimisticId);
    setMessages((prev) => [
      ...prev,
      buildOptimisticUserMessage({
        text,
        attached,
        optimisticId,
        createdAt,
      }),
    ]);
    newMessageCountRef.current += 1;
    return { optimisticId, dotsCurrent: sendStart.beginDots() };
  }, [setInput, setPendingAttachment, setMessages, newMessageCountRef, sendStart]);

  const restoreFailedSend = useRestoreFailedSend({
    token, setMessages, newMessageCountRef, pendingAttachmentRef, setPendingAttachment,
    stashAttachmentForThread, setPendingOutboundId, sendInFlightRef, setSendPhase,
  });

  /** A send to a chat that does not exist yet: it waits for the new chat's id. */
  const sendToNewChat = useCallback(
    async (send: PaintedSend, pending: ReturnType<typeof buildPendingSendAfterCreate>, giveBack: () => void) => {
      setSendPhase("creating");
      try {
        const id = await ensureChatId({
          isCurrent: send.isCurrentView,
          discard: discardEmptyChat,
          adopt: adoptComposerThread,
        });
        if (!id) giveBack();
        else setPendingSend({ chatId: id, session, originViewVersion: send.version, ...pending });
      } catch {
        giveBack();
        if (send.isCurrentView()) feedback?.error(t("chat.error_generic"));
      }
    },
    [ensureChatId, discardEmptyChat, adoptComposerThread, session, feedback, t],
  );

  const routeSend = useChatSendRoute({
    token, chatId, messages, selectedModel, imageGenerating, onGenerateImage, sendMessage, sendStart, updateUser, t,
    pendingAttachmentRef, setPendingAttachment, setPendingOutboundId, sendInFlightRef, setSendPhase,
    restoreFailedSend, sendToNewChat,
  });

  const handleSend = useCallback(
    async (overrideText?: string) => {
      const tappedAt = Date.now();
      const version = viewRef.current.version;
      const composerText = overrideText ?? inputRef.current;
      const text = composerText.trim();
      const verdict = canSend({
        sendInFlight: sendInFlightRef.current,
        chatLoading,
        chatId,
        routeChatId,
        isOffline,
        streaming,
        text,
        hasAttachment: Boolean(pendingAttachmentRef.current),
        token,
        creating: creatingRef.current,
        attachPicking: attachPickInFlightRef.current,
      });
      // Offline keeps the draft; banner + dimmed send already signal it. A modal
      // Alert feels unfinished without a send queue — use a soft toast instead.
      if (verdict === "offline") notifyOfflineSendBlocked({ warn: notifyWarning, showToast: onOfflineBlocked });
      if (verdict === "streaming") onStreamBusy?.();
      if (verdict !== "send") return;
      tap();
      const isCurrentSession = () => session === getSessionGeneration();
      const turn: SendTurn = {
        text,
        composerText,
        attachment: pendingAttachmentRef.current,
        threadKey: getThreadKey(),
        isCurrentSession,
        isCurrentView: () => isCurrentSession() && viewRef.current.version === version,
      };
      // Paint first: the bubble, an empty composer and typing dots in this
      // frame, before any network call. Where the turn goes is decided after.
      sendInFlightRef.current = true;
      setSendPhase(queryNeedsClientGeo(text) ? "locating" : turn.attachment ? "uploading" : "preparing");
      const painted = paintUserTurn(text, turn.attachment, tappedAt);
      await routeSend({ ...turn, ...painted, version });
    },
    [
      session, inputRef, chatLoading, chatId, routeChatId, isOffline, streaming, pendingAttachmentRef,
      token, creatingRef, attachPickInFlightRef, onOfflineBlocked, onStreamBusy, getThreadKey, paintUserTurn, routeSend,
    ],
  );

  const removePendingAttachment = useCallback(() => replacePendingAttachment(null), [replacePendingAttachment]);

  const viewVersion = viewRef.current.version;
  const restoreComposerDraft = useCallback((recovered: ComposerSendDraft): boolean => {
    if (session !== getSessionGeneration() || viewRef.current.version !== viewVersion ||
        getThreadKey() !== composerThread || sendInFlightRef.current || streaming || attachPickInFlightRef.current) return false;
    // A recovery action must never displace text or a file typed while the
    // rejected send was in flight. The caller keeps its queue until accepted.
    if (inputRef.current.length > 0 || pendingAttachmentRef.current) {
      feedback?.error(t("chat.restore_draft_blocked"));
      return false;
    }
    setInput(recovered.text);
    setPendingAttachment(recovered.attachment);
    return true;
  }, [
    session, viewVersion, getThreadKey, composerThread, streaming, inputRef, pendingAttachmentRef, feedback, t,
    setInput, setPendingAttachment, attachPickInFlightRef,
  ]);

  const { handleMathScanCaptured, readScan, handleMathScanSolve } = useMathScanSend({
    token,
    t,
    inputRef,
    setInput,
    replacePendingAttachment,
    setMathScannerOpen,
    handleSend,
  });

  return {
    setInput,
    pendingAttachment,
    setPendingAttachment,
    removePendingAttachment,
    attachPicking,
    sendPhase,
    attachSheetOpen,
    setAttachSheetOpen,
    mathScannerOpen,
    setMathScannerOpen,
    handleSend,
    restoreComposerDraft,
    handlePickAttachment,
    handleAttachmentSheetSelect,
    handleMathScanCaptured,
    readScan,
    handleMathScanSolve,
    creatingRef,
    pendingOutboundId,
  };
}
