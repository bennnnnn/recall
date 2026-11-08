import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "expo-router";

import { useComposerDraftApi } from "@/features/chat/context/ComposerDraftContext";
import { useActionFeedbackOptional } from "@/contexts/ActionFeedbackContext";

import type { useDraftChat } from "@/features/chat/hooks/useDraftChat";
import type { useChatScroll } from "@/features/chat/hooks/useChatScroll";
import { getSessionGeneration } from "@/lib/auth";
import type { Message } from "@/lib/api";
import { notifyWarning, tap } from "@/lib/haptics";
import { notifyOfflineSendBlocked } from "@/lib/offlineSendFeedback";
import {
  buildPendingSendAfterCreate,
  type ComposerSendDraft,
  type SendMessageOptions,
} from "@/features/chat/model/sendLogic";
import { canSend } from "@/features/chat/model/sendGuards";
import { useComposerAttachmentSheet } from "@/features/chat/hooks/useComposerAttachmentSheet";
import { useChatSendRoute, type PaintedSend } from "@/features/chat/hooks/useChatSendRoute";
import { usePaintUserTurn } from "@/features/chat/hooks/usePaintUserTurn";
import { useEnsureChatId } from "@/features/chat/hooks/useEnsureChatId";
import { useMathScanSend } from "@/features/chat/hooks/useMathScanSend";
import { useRestoreFailedSend, type SendTurn } from "@/features/chat/hooks/useRestoreFailedSend";
import { useSendAttachment } from "@/features/chat/hooks/useSendAttachment";
import type { SendTurnStart } from "@/features/chat/hooks/useTurnStart";
import { composerThreadKey } from "@/features/chat/model/composerThreadDraft";
import type { ImageGenSubmit } from "@/features/images/hooks/useImageGeneration";
import { type LocationSwitch, queryNeedsClientGeo } from "@/features/chat/model/resolveClientGeoForQuery";
import { useViewOwner } from "@/features/chat/hooks/useViewOwner";
import type { EditThread } from "@/features/chat/model/threadEdit";
import { discardDraftAttachment } from "@/features/attachments/model/attachments";
import {
  subscribeComposerAttachmentQueue,
  takeQueuedComposerAttachment,
} from "@/features/attachments/model/pendingComposerAttachment";

type Router = ReturnType<typeof useRouter>;
type DraftChat = ReturnType<typeof useDraftChat>;
type ChatScroll = ReturnType<typeof useChatScroll>;
type ChatSendPhase = "idle" | "locating" | "preparing" | "uploading" | "creating";

/** False when the chat refused the send before showing it, or Stop took it back before it went out. */
type SendMessageFn = (text: string, opts?: SendMessageOptions) => Promise<boolean>;

/** How `handleSend` treats the composer when it sends a given line instead of the composer's text. */
type SendLineOptions = {
  /**
   * A tapped line (a follow-up, a card's answer) is not the composer's: its half-typed
   * draft and file stay put. Without it the line stands in for the composer's text and
   * takes its file (a math scan's photo goes with its reading).
   */
  leaveComposer?: boolean;
};

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
  editThread: EditThread;
  /** Current transcript — a short follow-up after a picture is worth asking the server about. */
  messages: Message[];
  selectedModel: string;
  updateUser: (patch: Partial<import("@/lib/api").User>) => Promise<void>;
  /** The account's Location switch: a location question need not wait for an on one to save. */
  locationSwitch?: LocationSwitch;
  t: (key: string, options?: Record<string, unknown>) => string;
  onStreamBusy?: () => void;
  /** Soft offline cue (toast) — prefer over a blocking Alert; draft stays in the composer. */
  onOfflineBlocked?: () => void;
  isOffline: boolean;
  /** Runs before a send is painted (a window around a search hit goes to the newest page). */
  beforeSend?: () => Promise<void>;
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
  editThread,
  messages,
  selectedModel,
  updateUser,
  locationSwitch = "unknown",
  t,
  onStreamBusy,
  onOfflineBlocked,
  isOffline,
  beforeSend,
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
  // Bumped by each new account or composer thread and on unmount: a send from before lands nowhere.
  const viewRef = useRef({ version: 0 });
  useLayoutEffect(() => {
    viewRef.current.version += 1;
  }, [session, composerThread]);
  const { owns } = useViewOwner(`${session}:${composerThread}`);
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
  const signedIn = Boolean(token);
  useEffect(() => {
    const applyQueued = () => {
      if (!signedIn || session !== getSessionGeneration()) return;
      const next = takeQueuedComposerAttachment(composerThread);
      if (next) replacePendingAttachment(next);
    };
    applyQueued();
    return subscribeComposerAttachmentQueue(applyQueued);
  }, [composerThread, signedIn, session, replacePendingAttachment]);
  const restoreFailedSend = useRestoreFailedSend({
    token, editThread, newMessageCountRef, pendingAttachmentRef, setPendingAttachment,
    stashAttachmentForThread, setPendingOutboundId, sendInFlightRef, setSendPhase, t,
  });
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
      const sending = sendMessage(text, {
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
      // Refused before it showed: the draft comes back to the new chat's composer.
      const isCurrentSession = () => session === getSessionGeneration();
      const turn: SendTurn = {
        text: composerDraft.text.trim(),
        composerText: composerDraft.text,
        attachment: composerDraft.attachment,
        threadKey: chatId,
        isCurrentSession,
        isCurrentView: () => isCurrentSession() && getThreadKey() === chatId,
      };
      void sending.then((sent) => {
        if (!sent) restoreFailedSend(turn, trackSendingMessageId, composerDraft.attachment);
      });
    }
  }, [
    chatId, routeChatId, session, pendingSend, sendMessage, stashFailedDraftForThread, stashAttachmentForThread,
    getThreadKey, restoreFailedSend,
  ]);

  const { clearComposer, paintUserTurn } = usePaintUserTurn({
    setInput, setPendingAttachment, setPendingOutboundId, editThread, newMessageCountRef, sendStart,
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
    token, chatId, messages, selectedModel, imageGenerating, onGenerateImage, sendMessage, sendStart, updateUser,
    locationSwitch, t,
    pendingAttachmentRef, setPendingAttachment, setPendingOutboundId, sendInFlightRef, setSendPhase,
    restoreFailedSend, sendToNewChat,
  });

  /** False when the send was refused before its bubble painted (offline, another send preparing). */
  const handleSend = useCallback(
    async (overrideText?: string, options?: SendLineOptions): Promise<boolean> => {
      const tappedAt = Date.now();
      const version = viewRef.current.version;
      const composerText = overrideText ?? inputRef.current;
      const text = composerText.trim();
      const leavesComposer = overrideText !== undefined && options?.leaveComposer === true;
      const attachment = leavesComposer ? null : pendingAttachmentRef.current;
      const verdict = canSend({
        sendInFlight: sendInFlightRef.current,
        chatLoading,
        chatId,
        routeChatId,
        isOffline,
        streaming,
        text,
        hasAttachment: Boolean(attachment),
        token,
        creating: creatingRef.current,
        attachPicking: attachPickInFlightRef.current,
      });
      // Offline keeps the draft; banner + dimmed send already signal it. A modal
      // Alert feels unfinished without a send queue — use a soft toast instead.
      if (verdict === "offline") notifyOfflineSendBlocked({ warn: notifyWarning, showToast: onOfflineBlocked });
      if (verdict === "streaming") onStreamBusy?.();
      if (verdict !== "send") return false;
      tap();
      const isCurrentSession = () => session === getSessionGeneration();
      const turn: SendTurn = {
        text,
        composerText,
        attachment,
        threadKey: getThreadKey(),
        isCurrentSession,
        isCurrentView: () => isCurrentSession() && viewRef.current.version === version,
        leavesComposer,
      };
      // A send from a window waits for the newest page. The field empties at the tap, as any
      // send's does: this send is what it held then, and text typed meanwhile is the next draft.
      const clearedAtTap = Boolean(beforeSend) && !leavesComposer;
      if (beforeSend) {
        if (clearedAtTap) clearComposer();
        sendInFlightRef.current = true;
        // Send shows busy: an idle button refused the next tap without a word.
        setSendPhase("preparing");
        try {
          await beforeSend();
        } finally {
          sendInFlightRef.current = false;
        }
        // Another chat or account opened meanwhile: the text goes back to the chat it was typed in.
        if (!turn.isCurrentView()) {
          restoreFailedSend(turn, `local-${tappedAt}`, turn.attachment);
          return false;
        }
      }
      // Paint first: the bubble, an empty composer and typing dots in this
      // frame, before any network call. Where the turn goes is decided after.
      sendInFlightRef.current = true;
      setSendPhase(queryNeedsClientGeo(text) ? "locating" : turn.attachment ? "uploading" : "preparing");
      const painted = paintUserTurn(
        text, turn.attachment, tappedAt, leavesComposer ? "leave" : clearedAtTap ? "cleared" : "clear",
      );
      await routeSend({ ...turn, ...painted, version });
      return true;
    },
    [
      session, inputRef, chatLoading, chatId, routeChatId, isOffline, streaming, pendingAttachmentRef,
      token, creatingRef, attachPickInFlightRef, onOfflineBlocked, onStreamBusy, getThreadKey, paintUserTurn, routeSend,
      beforeSend, clearComposer, restoreFailedSend,
    ],
  );

  // A tapped line (a follow-up, a clarify card's picks) leaves the half-typed draft and file.
  const sendTappedLine = useCallback((line: string) => handleSend(line, { leaveComposer: true }), [handleSend]);

  const removePendingAttachment = useCallback(() => replacePendingAttachment(null), [replacePendingAttachment]);

  const restoreComposerDraft = useCallback((recovered: ComposerSendDraft): boolean => {
    if (session !== getSessionGeneration() || !owns() ||
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
    session, owns, getThreadKey, composerThread, streaming, inputRef, pendingAttachmentRef, feedback, t,
    setInput, setPendingAttachment, attachPickInFlightRef,
  ]);

  const { handleMathScanCaptured } = useMathScanSend({
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
    sendTappedLine,
    restoreComposerDraft,
    handlePickAttachment,
    handleAttachmentSheetSelect,
    handleMathScanCaptured,
    creatingRef,
    pendingOutboundId,
  };
}
