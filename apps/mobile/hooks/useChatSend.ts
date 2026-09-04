import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Keyboard } from "react-native";
import { useRouter } from "expo-router";

import { useComposerDraftApi } from "@/contexts/ComposerDraftContext";
import { useActionFeedbackOptional } from "@/contexts/ActionFeedbackContext";
import { reportRecoverableWarning } from "@/lib/reportRecoverableError";

import type { AttachmentSource } from "@/components/AttachmentSourceSheet";
import type { useDraftChat } from "@/hooks/useDraftChat";
import type { useChatScroll } from "@/hooks/useChatScroll";
import { getSessionGeneration } from "@/lib/auth";
import type { Message } from "@/lib/api";
import { notifyWarning, tap } from "@/lib/haptics";
import { notifyOfflineSendBlocked } from "@/lib/offlineSendFeedback";
import {
  buildOptimisticUserMessage,
  buildPendingSendAfterCreate,
  shouldBlockSend,
  type ComposerSendDraft,
} from "@/lib/chat/chatSendLogic";
import { composerThreadKey, shouldRestoreFailedSend } from "@/lib/chat/composerThreadDraft";
import { flushEmailDrafts } from "@/lib/emailDraftFlush";
import {
  extractImageGenPrompt,
  extractAttachedImageEditPrompt,
  extractImageRevisionPrompt,
  imageGenRevisionContext,
} from "@/lib/imageGenIntent";
import { scheduleIdlePromise } from "@/lib/scheduleIdle";
import type { ClientGeo } from "@/lib/clientGeo";
import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";
import {
  pickDocument,
  HeicUnsupportedError,
  pickFromCamera,
  pickFromPhotoLibrary,
  uploadChatAttachment,
  defaultMathCameraPrompt,
  type PendingAttachment,
} from "@/lib/attachments";
import {
  subscribeComposerAttachmentQueue,
  takeQueuedComposerAttachment,
} from "@/lib/pendingComposerAttachment";

type Router = ReturnType<typeof useRouter>;
type DraftChat = ReturnType<typeof useDraftChat>;
type ChatScroll = ReturnType<typeof useChatScroll>;
export type ChatSendPhase = "idle" | "preparing" | "uploading" | "creating";

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
  /** Current transcript — used to treat short follow-ups after image replies as revisions. */
  messages: Message[];
  selectedModel: string;
  user: import("@/lib/api").User | null;
  updateUser: (patch: Partial<import("@/lib/api").User>) => Promise<void>;
  t: (key: string) => string;
  onStreamBusy?: () => void;
  /** Soft offline cue (toast) — prefer over a blocking Alert; draft stays in the composer. */
  onOfflineBlocked?: () => void;
  isOffline: boolean;
  resolveQuizProjectId?: () => string | null;
  onBeforeSend?: (text: string) => boolean | void;
  /** Run image generation for detected image-intent text (no confirmation sheet). */
  onGenerateImage?: (prompt: string, userMessage: string, reference?: { attachment?: PendingAttachment; ids?: string[] }) => void;
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
  setMessages,
  messages,
  selectedModel,
  updateUser,
  t,
  onStreamBusy,
  onOfflineBlocked,
  isOffline,
  resolveQuizProjectId,
  onBeforeSend,
  onGenerateImage,
  imageGenerating = false,
}: Options) {
  const {
    draftChatIdRef,
    skipLoadForChatIdRef,
    creatingRef,
    prepareDraftChat,
    setDraftChatId,
    discardEmptyChat,
  } = draft;
  const { newMessageCountRef } = scroll;

  const {
    setInput,
    inputRef,
    switchThread,
    adoptComposerThread,
    stashFailedDraftForThread,
    getThreadKey,
  } = useComposerDraftApi();
  const feedback = useActionFeedbackOptional();
  const [pendingAttachment, setPendingAttachmentState] = useState<PendingAttachment | null>(null);
  const pendingAttachmentRef = useRef<PendingAttachment | null>(null);
  const setPendingAttachment = useCallback((value: React.SetStateAction<PendingAttachment | null>) => {
    const next = typeof value === "function" ? value(pendingAttachmentRef.current) : value;
    pendingAttachmentRef.current = next;
    setPendingAttachmentState(next);
  }, []);
  const attachBusy = false;
  const [attachPicking, setAttachPicking] = useState(false);
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

  const attachPickInFlightRef = useRef(false);
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

  const prevComposerThreadRef = useRef(composerThread);
  const prevSessionRef = useRef(session);
  useLayoutEffect(() => {
    const fromKey = getThreadKey();
    switchThread(composerThread);
    const accountChanged = prevSessionRef.current !== session;
    prevSessionRef.current = session;
    if (!accountChanged && prevComposerThreadRef.current === composerThread) return;
    prevComposerThreadRef.current = composerThread;
    sendInFlightRef.current = false;
    setSendPhase("idle");
    setPendingOutboundId(null);
    if (!accountChanged && fromKey === composerThread) return;
    setPendingAttachment(null);
    setAttachSheetOpen(false);
    setMathScannerOpen(false);
  }, [composerThread, session, switchThread, getThreadKey, setPendingAttachment]);
  useEffect(() => {
    const applyQueued = () => {
      if (!token || session !== getSessionGeneration()) return;
      const next = takeQueuedComposerAttachment(composerThread);
      if (next) setPendingAttachment(next);
    };
    applyQueued();
    return subscribeComposerAttachmentQueue(applyQueued);
  }, [composerThread, token, session, setPendingAttachment]);
  useEffect(() => {
    if (
      pendingSend &&
      (session !== pendingSend.session ||
        (routeChatId != null
          ? routeChatId !== pendingSend.chatId
          : viewRef.current.version !== pendingSend.originViewVersion))
    ) {
      if (session === pendingSend.session) stashFailedDraftForThread(pendingSend.chatId, pendingSend.text);
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
  }, [chatId, routeChatId, session, pendingSend, sendMessage, stashFailedDraftForThread]);

  const handleSend = useCallback(
    async (overrideText?: string) => {
      if (
        sendInFlightRef.current || chatLoading ||
        (routeChatId != null && routeChatId !== chatId)
      ) return;
      const version = viewRef.current.version;
      const isCurrentSession = () => session === getSessionGeneration();
      const isCurrentView = () => isCurrentSession() && viewRef.current.version === version;
      const composerText = overrideText ?? inputRef.current;
      const text = composerText.trim();
      if (isOffline) {
        // Keep the draft; banner + dimmed send already signal offline. A modal
        // Alert feels unfinished without a send queue — use a soft toast instead.
        notifyOfflineSendBlocked({
          warn: notifyWarning,
          showToast: onOfflineBlocked,
        });
        return;
      }
      if (streaming && (text || pendingAttachment)) {
        onStreamBusy?.();
        return;
      }
      if (
        shouldBlockSend({
          text,
          hasAttachment: Boolean(pendingAttachment),
          streaming,
          token,
          creating: creatingRef.current,
          attachBusy,
          isOffline,
        })
      )
        return;
      tap();
      if (onBeforeSend?.(text) === true) return;

      // Image-gen intent → /images/generate from the composer (no sheet, no LLM stub).
      // Do not gate on client isPro — plan can be stale while the API still knows Pro;
      // submitPrompt / the API open upgrade or generate. Never let the model invent
      // "the app will attach an image shortly" without calling generate.
      if (onGenerateImage && (!pendingAttachment || pendingAttachment.kind === "image")) {
        const revisionContext = imageGenRevisionContext(messages);
        const revision = pendingAttachment?.kind === "image"
          ? extractAttachedImageEditPrompt(text)
          : extractImageRevisionPrompt(text, revisionContext);
        const imagePrompt = extractImageGenPrompt(text) ?? revision;
        if (imagePrompt) {
          if (imageGenerating) return;
          sendInFlightRef.current = true;
          setSendPhase("preparing");
          const draftsSaved = await flushEmailDrafts();
          if (!isCurrentView()) return;
          sendInFlightRef.current = false;
          setSendPhase("idle");
          if (!draftsSaved) return;
          setInput("");
          setPendingAttachment(null);
          Keyboard.dismiss();
          const reference = pendingAttachment ? { attachment: pendingAttachment }
            : revision && revisionContext.referenceAttachmentId
              ? { ids: [revisionContext.referenceAttachmentId] } : undefined;
          if (reference) onGenerateImage(imagePrompt, text, reference);
          else onGenerateImage(imagePrompt, text);
          return;
        }
      }

      const authToken = token;
      if (!authToken) return;

      let attached = pendingAttachment;
      const sendThreadKey = getThreadKey();
      sendInFlightRef.current = true;
      setSendPhase(attached ? "uploading" : "preparing");
      const draftsSaved = await flushEmailDrafts();
      if (!isCurrentView()) return;
      if (!draftsSaved) {
        sendInFlightRef.current = false;
        setSendPhase("idle");
        return;
      }
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

      const restoreDraft = () => {
        if (!isCurrentSession()) return;
        if (!isCurrentView()) {
          stashFailedDraftForThread(sendThreadKey, text);
          return;
        }
        setPendingOutboundId(null);
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
        newMessageCountRef.current = Math.max(0, newMessageCountRef.current - 1);
        if (getThreadKey() === sendThreadKey) {
          if (!pendingAttachmentRef.current && shouldRestoreFailedSend(inputRef.current, text)) {
            setInput(text);
            setPendingAttachment(attached);
          }
        } else {
          stashFailedDraftForThread(sendThreadKey, text);
        }
        sendInFlightRef.current = false;
        setSendPhase("idle");
      };

      let attachmentIds: string[] | undefined;
      if (attached) {
        try {
          const id = await uploadChatAttachment(authToken, attached);
          attachmentIds = [id];
          attached = { ...attached, existingAttachmentId: id };
          if (!isCurrentView()) {
            restoreDraft();
            return;
          }
        } catch (error) {
          restoreDraft();
          if (isCurrentView()) feedback?.error(
            error instanceof Error ? error.message : t("chat.attach_failed"),
          );
          return;
        }
      }

      const geoResult = await resolveClientGeoForQuery(authToken, text, t, updateUser);
      if (!geoResult.ok || !isCurrentView()) {
        restoreDraft();
        return;
      }
      const clientGeo = geoResult.clientGeo;

      if (!chatId) {
        creatingRef.current = true;
        setSendPhase("creating");
        try {
          const id = await prepareDraftChat(undefined, selectedModel);
          if (!id) throw new Error("Could not create chat");
          if (!isCurrentView()) {
            if (draftChatIdRef.current === id) {
              draftChatIdRef.current = null;
              setDraftChatId(null);
            }
            discardEmptyChat(id);
            restoreDraft();
            return;
          }
          skipLoadForChatIdRef.current = id;
          setChatTitle(null);
          setChatId(id);
          draftChatIdRef.current = null;
          setDraftChatId(null);
          adoptComposerThread(id);
          router.setParams({ chatId: id });
          setPendingSend({
            chatId: id,
            session,
            originViewVersion: version,
            ...buildPendingSendAfterCreate({
              text,
              composerText,
              attached,
              attachmentIds,
              optimisticId,
              clientGeo,
              model: selectedModel,
            }),
          });
        } catch {
          restoreDraft();
          if (isCurrentView()) feedback?.error(t("chat.error_generic"));
        } finally {
          creatingRef.current = false;
        }
        return;
      }
      const pending = buildPendingSendAfterCreate({
        text,
        composerText,
        attached,
        attachmentIds,
        optimisticId,
        clientGeo,
        model: selectedModel,
      });
      sendMessage(pending.text, pending);
      setPendingOutboundId(null);
      sendInFlightRef.current = false;
      setSendPhase("idle");
    },
    [
      pendingAttachment,
      setPendingAttachment,
      session,
      inputRef,
      setInput,
      streaming,
      token,
      creatingRef,
      attachBusy,
      chatId,
      chatLoading,
      routeChatId,
      newMessageCountRef,
      selectedModel,
      setMessages,
      prepareDraftChat,
      skipLoadForChatIdRef,
      draftChatIdRef,
      setDraftChatId,
      discardEmptyChat,
      router,
      sendMessage,
      updateUser,
      t,
      onStreamBusy,
      onOfflineBlocked,
      isOffline,
      onBeforeSend,
      onGenerateImage,
      imageGenerating,
      messages,
      feedback,
      setChatId,
      setChatTitle,
      getThreadKey,
      stashFailedDraftForThread,
      adoptComposerThread,
    ],
  );

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
  }, [session, viewVersion, getThreadKey, composerThread, streaming, inputRef, feedback, t, setInput, setPendingAttachment]);

  const handlePickAttachment = useCallback(() => {
    if (!token || attachBusy || streaming || sendInFlightRef.current) return;
    Keyboard.dismiss();
    // Let the keyboard finish dismissing before presenting the Modal so the
    // first tap isn't swallowed on Android.
    const version = viewRef.current.version;
    requestAnimationFrame(() => {
      if (viewRef.current.version === version && session === getSessionGeneration()) setAttachSheetOpen(true);
    });
  }, [token, attachBusy, streaming, session]);

  const waitForPickerUi = useCallback(() => scheduleIdlePromise(), []);

  const handleAttachmentSheetSelect = useCallback(
    async (source: AttachmentSource) => {
      if (
        attachPickInFlightRef.current ||
        !token ||
        attachBusy ||
        streaming ||
        sendInFlightRef.current
      )
        return;
      const version = viewRef.current.version;
      const current = () => viewRef.current.version === version && session === getSessionGeneration();
      attachPickInFlightRef.current = true;
      setAttachPicking(true);
      setAttachSheetOpen(false);
      await waitForPickerUi();

      if (!current() || !token || attachBusy || streaming || sendInFlightRef.current) {
        attachPickInFlightRef.current = false;
        setAttachPicking(false);
        return;
      }

      try {
        if (source === "solve_math_camera") {
          setMathScannerOpen(true);
          return;
        }
        if (source === "library") {
          router.push({ pathname: "/gallery", params: { pick: "1", composerThread } });
          return;
        }
        const picked =
          source === "camera"
            ? await pickFromCamera()
            : source === "photo"
              ? await pickFromPhotoLibrary()
              : await pickDocument();
        if (picked && current()) {
          setPendingAttachment(picked);
        }
      } catch (error) {
        if (!current()) return;
        if (error instanceof HeicUnsupportedError) {
          reportRecoverableWarning(feedback, t("chat.heic_unsupported_body"));
        } else {
          feedback?.error(
            error instanceof Error ? error.message : t("chat.attach_failed"),
          );
        }
      } finally {
        attachPickInFlightRef.current = false;
        setAttachPicking(false);
      }
    },
    [attachBusy, composerThread, feedback, router, session, streaming, t, token, waitForPickerUi, setPendingAttachment],
  );

  const handleMathScanCaptured = useCallback((pending: PendingAttachment) => {
    setPendingAttachment(pending);
    setInput(defaultMathCameraPrompt());
    setMathScannerOpen(false);
  }, [setInput, setPendingAttachment]);

  return {
    setInput,
    pendingAttachment,
    setPendingAttachment,
    attachBusy,
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
    creatingRef,
    pendingOutboundId,
  };
}
