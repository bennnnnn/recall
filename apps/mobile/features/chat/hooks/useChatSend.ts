import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Keyboard } from "react-native";
import { useRouter } from "expo-router";

import { useComposerDraftApi } from "@/contexts/ComposerDraftContext";
import { useActionFeedbackOptional } from "@/contexts/ActionFeedbackContext";

import type { useDraftChat } from "@/hooks/useDraftChat";
import type { useChatScroll } from "@/features/chat/hooks/useChatScroll";
import { getSessionGeneration } from "@/lib/auth";
import type { Message, ScanReading } from "@/lib/api";
import { clearPendingChatTtft } from "@/features/chat/model/latency";
import { notifyWarning, tap } from "@/lib/haptics";
import { notifyOfflineSendBlocked } from "@/lib/offlineSendFeedback";
import {
  buildOptimisticUserMessage,
  buildPendingSendAfterCreate,
  type ComposerSendDraft,
} from "@/features/chat/model/sendLogic";
import { canSend } from "@/features/chat/model/sendGuards";
import { resolveSendIntercept, type SendIntercept } from "@/features/chat/model/sendIntercept";
import { useEnsureChatId } from "@/features/chat/hooks/useEnsureChatId";
import { uploadSendAttachment, useSendAttachment } from "@/features/chat/hooks/useSendAttachment";
import { useComposerAttachmentPick } from "@/features/chat/hooks/useComposerAttachmentPick";
import { composerThreadKey, shouldRestoreFailedSend } from "@/features/chat/model/composerThreadDraft";
import { flushEmailDrafts } from "@/features/drafts/model/emailDraftFlush";
import type { ClientGeo } from "@/lib/clientGeo";
import {
  queryNeedsClientGeo,
  resolveClientGeoForQuery,
} from "@/lib/resolveClientGeoForQuery";
import { discardDraftAttachment, type PendingAttachment } from "@/features/attachments/model/attachments";
import { attachmentErrorMessage } from "@/features/attachments/model/attachmentErrors";
import {
  composerTextAfterScanConfirm,
  type ReadBackSubject,
  scanSolveMessage,
} from "@/lib/scanner/readBack";
import {
  composerTextAfterSubjectScan,
  type ScannerSubject,
} from "@/lib/scanner/subjects";
import {
  scanFailureDetail,
  scanFailureMessageKey,
  type ScanReadFailure,
} from "@/lib/scanner/scanReadError";
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

type SendMessageFn = (
  text: string,
  opts?: {
    skipUserBubble?: boolean;
    trackSendingMessageId?: string;
    attachmentIds?: string[];
    localImageUri?: string | null;
    localFileUri?: string | null;
    localFileName?: string | null;
    localFileContentType?: string | null;
    model?: string;
    clientGeo?: ClientGeo | null;
    composerDraft?: ComposerSendDraft;
  },
) => void;

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
  onBeforeSend?: (text: string) => boolean | void;
  /** Run image generation for detected image-intent text (no confirmation sheet). */
  onGenerateImage?: (
    prompt: string,
    userMessage: string,
    reference?: { attachment?: PendingAttachment; ids?: string[] },
    persistence?: {
      ready: Promise<boolean>;
      onFailure: () => void;
    },
  ) => void;
  imageGenerating?: boolean;
};

/** One send, from the tap that started it. */
type SendTurn = {
  text: string;
  composerText: string;
  attachment: PendingAttachment | null;
  threadKey: string;
  isCurrentSession: () => boolean;
  isCurrentView: () => boolean;
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
  setMessages,
  messages,
  selectedModel,
  updateUser,
  t,
  onStreamBusy,
  onOfflineBlocked,
  isOffline,
  onBeforeSend,
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
  const [attachSheetOpen, setAttachSheetOpen] = useState(false);
  const [mathScannerOpen, setMathScannerOpen] = useState(false);
  const [pendingOutboundId, setPendingOutboundId] = useState<string | null>(null);
  const [pendingSend, setPendingSend] = useState<{
    chatId: string;
    session: number;
    originViewVersion: number;
    text: string;
    skipUserBubble?: boolean;
    trackSendingMessageId?: string;
    attachmentIds?: string[];
    localImageUri?: string | null;
    localFileUri?: string | null;
    localFileName?: string | null;
    localFileContentType?: string | null;
    clientGeo?: ClientGeo | null;
    composerDraft: ComposerSendDraft;
    model: string;
  } | null>(null);

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
  const { attachPicking, attachPickInFlightRef, handlePickAttachment, handleAttachmentSheetSelect } =
    useComposerAttachmentPick({
      token, streaming, session, viewRef, sendInFlightRef, feedback, t, replacePendingAttachment,
      setAttachSheetOpen, setMathScannerOpen,
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
  }, [composerThread, session, switchThread, getThreadKey, switchAttachmentThread, resetForNewSession, resetAttachmentDrafts]);
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

  /** Hands an image request to generation; persistence failure brings the draft back. */
  const generateFromComposer = useCallback(
    (intercept: Extract<SendIntercept, { kind: "generate" }>, turn: SendTurn) => {
      const draftsPromise = flushEmailDrafts();
      setInput("");
      setPendingAttachment(null);
      Keyboard.dismiss();
      const restoreImageDraft = () => {
        if (!turn.isCurrentSession()) return;
        if (!turn.isCurrentView() || getThreadKey() !== turn.threadKey) {
          stashFailedDraftForThread(turn.threadKey, turn.composerText);
          return;
        }
        if (
          !pendingAttachmentRef.current &&
          shouldRestoreFailedSend(inputRef.current, turn.composerText)
        ) {
          setInput(turn.composerText);
          setPendingAttachment(turn.attachment);
          return;
        }
        feedback?.error(t("chat.restore_draft_blocked"));
      };
      onGenerateImage?.(intercept.prompt, turn.text, intercept.reference, {
        ready: draftsPromise,
        onFailure: restoreImageDraft,
      });
      sendInFlightRef.current = false;
      setSendPhase("idle");
    },
    [setInput, setPendingAttachment, pendingAttachmentRef, getThreadKey, stashFailedDraftForThread, inputRef, feedback, t, onGenerateImage],
  );

  /** Clears the composer and paints the user's bubble; returns its id. */
  const paintUserTurn = useCallback((text: string, attached: PendingAttachment | null) => {
    // Clear the composer immediately so the next draft can be typed.
    // Keep Send/Attach busy until the turn is accepted — an idle button
    // with sendInFlightRef set looked finished and ate the next tap.
    setInput("");
    setPendingAttachment(null);
    Keyboard.dismiss();

    const optimisticId = `local-${Date.now()}`;
    const createdAt = new Date().toISOString();
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
    return optimisticId;
  }, [setInput, setPendingAttachment, setMessages, newMessageCountRef]);

  /** Takes the bubble back and returns the draft to the thread it was typed in. */
  const restoreFailedSend = useCallback(
    (turn: SendTurn, optimisticId: string, attached: PendingAttachment | null) => {
      clearPendingChatTtft(optimisticId);
      if (!turn.isCurrentSession()) {
        discardDraftAttachment(null, attached);
        return;
      }
      // The attachment travels with the text: uploaded, it keeps its id for the next send.
      const stash = () => {
        stashFailedDraftForThread(turn.threadKey, turn.text);
        stashAttachmentForThread(turn.threadKey, getThreadKey(), attached);
      };
      if (!turn.isCurrentView()) {
        stash();
        return;
      }
      setPendingOutboundId(null);
      setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
      newMessageCountRef.current = Math.max(0, newMessageCountRef.current - 1);
      if (getThreadKey() === turn.threadKey) {
        if (!pendingAttachmentRef.current && shouldRestoreFailedSend(inputRef.current, turn.text)) {
          setInput(turn.text);
          setPendingAttachment(attached);
        } else {
          discardDraftAttachment(token, attached);
        }
      } else {
        stash();
      }
      sendInFlightRef.current = false;
      setSendPhase("idle");
    },
    [stashFailedDraftForThread, stashAttachmentForThread, setMessages, newMessageCountRef, getThreadKey, pendingAttachmentRef, inputRef, setInput, setPendingAttachment, token],
  );

  const handleSend = useCallback(
    async (overrideText?: string) => {
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
      if (onBeforeSend?.(text) === true) return;
      const isCurrentSession = () => session === getSessionGeneration();
      const turn: SendTurn = {
        text,
        composerText,
        attachment: pendingAttachmentRef.current,
        threadKey: getThreadKey(),
        isCurrentSession,
        isCurrentView: () => isCurrentSession() && viewRef.current.version === version,
      };

      const deciding = resolveSendIntercept({
        text,
        attachment: turn.attachment,
        chatId,
        messages,
        canGenerate: Boolean(onGenerateImage),
        imageGenerating,
        token,
        isCurrentView: turn.isCurrentView,
        onServerCheck: () => {
          sendInFlightRef.current = true;
          setSendPhase("preparing");
        },
      });
      const intercept = deciding instanceof Promise ? await deciding : deciding;
      if (intercept.kind === "drop" || intercept.kind === "stale") {
        sendInFlightRef.current = false;
        setSendPhase("idle");
        return;
      }
      if (intercept.kind === "generate") {
        generateFromComposer(intercept, turn);
        return;
      }

      const authToken = token;
      if (!authToken) return;
      let attached = turn.attachment;
      sendInFlightRef.current = true;
      setSendPhase(
        queryNeedsClientGeo(text) ? "locating" : attached ? "uploading" : "preparing",
      );
      // Geo intents: resolve the OS permission before painting anything, so a
      // deny never makes a just-painted bubble vanish. Instant for non-geo text.
      const geoResult = await resolveClientGeoForQuery(authToken, text, t, updateUser);
      if (!geoResult.ok || !turn.isCurrentView()) {
        sendInFlightRef.current = false;
        setSendPhase("idle");
        return;
      }
      setSendPhase(attached ? "uploading" : "preparing");
      const optimisticId = paintUserTurn(text, attached);
      const restoreDraft = () => restoreFailedSend(turn, optimisticId, attached);

      // Flush in-progress email card edits in parallel with the attachment
      // upload instead of blocking the optimistic bubble on the flush.
      const draftsPromise = flushEmailDrafts();
      let attachmentIds: string[] | undefined;
      if (attached) {
        try {
          ({ ids: attachmentIds, attachment: attached } = await uploadSendAttachment(authToken, attached));
          if (!turn.isCurrentView()) {
            restoreDraft();
            return;
          }
        } catch (error) {
          restoreDraft();
          if (turn.isCurrentView()) feedback?.error(attachmentErrorMessage(error, t));
          return;
        }
      }
      const draftsSaved = await draftsPromise;
      if (!turn.isCurrentView()) return;
      if (!draftsSaved) {
        restoreDraft();
        return;
      }

      const pending = buildPendingSendAfterCreate({
        text,
        composerText,
        attached,
        attachmentIds,
        optimisticId,
        clientGeo: geoResult.clientGeo,
        model: selectedModel,
      });
      if (chatId) {
        sendMessage(pending.text, pending);
        setPendingOutboundId(null);
        sendInFlightRef.current = false;
        setSendPhase("idle");
        return;
      }
      setSendPhase("creating");
      try {
        const id = await ensureChatId({
          isCurrent: turn.isCurrentView,
          discard: discardEmptyChat,
          adopt: adoptComposerThread,
        });
        if (!id) restoreDraft();
        else setPendingSend({ chatId: id, session, originViewVersion: version, ...pending });
      } catch {
        restoreDraft();
        if (turn.isCurrentView()) feedback?.error(t("chat.error_generic"));
      }
    },
    [
      session, inputRef, chatLoading, chatId, routeChatId, isOffline, streaming, pendingAttachmentRef,
      token, creatingRef, attachPickInFlightRef, onOfflineBlocked, onStreamBusy, onBeforeSend, getThreadKey,
      messages, onGenerateImage, imageGenerating, generateFromComposer, t, updateUser, paintUserTurn,
      restoreFailedSend, feedback, selectedModel, sendMessage, ensureChatId, discardEmptyChat,
      adoptComposerThread,
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
  }, [session, viewVersion, getThreadKey, composerThread, streaming, attachPickInFlightRef, inputRef, pendingAttachmentRef, feedback, t, setInput, setPendingAttachment]);

  const handleMathScanCaptured = useCallback((
    pending: PendingAttachment,
    subject: ScannerSubject,
    confirmedReading?: string,
  ) => {
    replacePendingAttachment(pending);
    // A checked reading rides with the photo so the API solves what the
    // student confirmed instead of reading the photo again.
    const text = confirmedReading
      ? withComposerDraft(composerTextAfterScanConfirm(confirmedReading, subject), inputRef.current)
      : composerTextAfterSubjectScan(inputRef.current, subject);
    setInput(text);
    setMathScannerOpen(false);
    void handleSend(text);
  }, [handleSend, setInput, replacePendingAttachment, inputRef]);

  const readScan = useCallback(
    async (
      scan: PendingAttachment,
      subject: ReadBackSubject,
      signal: AbortSignal,
    ): Promise<ScanReading | ScanReadFailure | null> => {
      if (!token) return null;
      try {
        // Loaded on use: the API barrel pulls in native file-system modules
        // this hook otherwise never touches.
        const { api } = await import("@/lib/api");
        return await api.readScan(token, subject, scan, signal);
      } catch (error) {
        // Every subject names a missing reader, an oversized photo and a
        // limit the same way. Anything else stays generic.
        const detail = scanFailureDetail(error);
        if (!detail) return null;
        const key = scanFailureMessageKey(detail);
        return { error: key ? t(key) : detail };
      }
    },
    [t, token],
  );

  const handleMathScanSolve = useCallback((reading: string, subject: ScannerSubject = "math") => {
    setMathScannerOpen(false);
    const message = scanSolveMessage(reading, subject);
    if (!message) return;
    const text = withComposerDraft(message, inputRef.current);
    setInput(text);
    void handleSend(text);
  }, [handleSend, setInput, inputRef]);

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

/** Keep what the student had already typed, after the scan's own text. */
function withComposerDraft(text: string, draft: string): string {
  const kept = draft.trim();
  return kept ? `${text}\n\n${kept}` : text;
}
