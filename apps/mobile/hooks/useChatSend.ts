import { useCallback, useEffect, useRef, useState } from "react";
import { Keyboard } from "react-native";
import { useRouter } from "expo-router";

import { useComposerDraftApi } from "@/contexts/ComposerDraftContext";
import { useActionFeedbackOptional } from "@/contexts/ActionFeedbackContext";
import { reportRecoverableWarning } from "@/lib/reportRecoverableError";

type Router = ReturnType<typeof useRouter>;

import type { AttachmentSource } from "@/components/AttachmentSourceSheet";
import type { useDraftChat } from "@/hooks/useDraftChat";
import type { useChatScroll } from "@/hooks/useChatScroll";
import type { Message } from "@/lib/api";
import { notifyWarning, tap } from "@/lib/haptics";
import { notifyOfflineSendBlocked } from "@/lib/offlineSendFeedback";
import { parseUserMessageContent } from "@/lib/messageAttachments";
import {
  buildOptimisticUserMessage,
  buildPendingSendAfterCreate,
  shouldBlockSend,
} from "@/lib/chat/chatSendLogic";
import {
  extractImageGenPrompt,
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
  },
) => void;

type Options = {
  token: string | null;
  chatId: string | null;
  setChatId: React.Dispatch<React.SetStateAction<string | null>>;
  setChatTitle: React.Dispatch<React.SetStateAction<string | null>>;
  router: Router;
  draft: DraftChat;
  scroll: ChatScroll;
  streaming: boolean;
  sendMessage: SendMessageFn;
  editMessage: (id: string, text: string, model: string, clientGeo?: ClientGeo | null) => void;
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
  onGenerateImage?: (prompt: string, userMessage: string) => void;
  imageGenerating?: boolean;
};

export function useChatSend({
  token,
  chatId,
  setChatId,
  setChatTitle,
  router,
  draft,
  scroll,
  streaming,
  sendMessage,
  editMessage,
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
  } = draft;
  const { newMessageCountRef } = scroll;

  const { setInput, inputRef } = useComposerDraftApi();
  const feedback = useActionFeedbackOptional();
  const [pendingAttachment, setPendingAttachment] = useState<PendingAttachment | null>(null);
  const attachBusy = false;
  const [attachPicking, setAttachPicking] = useState(false);
  const [sendPhase, setSendPhase] = useState<ChatSendPhase>("idle");
  const [attachSheetOpen, setAttachSheetOpen] = useState(false);
  const [mathScannerOpen, setMathScannerOpen] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [pendingOutboundId, setPendingOutboundId] = useState<string | null>(null);
  const [pendingSend, setPendingSend] = useState<{
    text: string;
    skipUserBubble?: boolean;
    trackSendingMessageId?: string;
    attachmentIds?: string[];
    localImageUri?: string | null;
    localFileUri?: string | null;
    localFileName?: string | null;
    localFileContentType?: string | null;
    clientGeo?: ClientGeo | null;
    model: string;
  } | null>(null);

  const attachPickInFlightRef = useRef(false);
  const sendInFlightRef = useRef(false);
  useEffect(() => {
    const applyQueued = () => {
      const next = takeQueuedComposerAttachment();
      if (next) setPendingAttachment(next);
    };
    applyQueued();
    return subscribeComposerAttachmentQueue(applyQueued);
  }, []);
  useEffect(() => {
    if (chatId && pendingSend) {
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
      });
      setPendingOutboundId(null);
      sendInFlightRef.current = false;
      setSendPhase("idle");
    }
  }, [chatId, pendingSend, sendMessage]);

  const handleSend = useCallback(
    async (overrideText?: string) => {
      if (sendInFlightRef.current) return;
      const text = (overrideText ?? inputRef.current).trim();
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
      if (editingMessageId && pendingAttachment) {
        reportRecoverableWarning(feedback, t("chat.edit_no_attachments"));
        return;
      }
      tap();
      if (onBeforeSend?.(text) === true) return;

      // Image-gen intent → /images/generate from the composer (no sheet, no LLM stub).
      // Do not gate on client isPro — plan can be stale while the API still knows Pro;
      // submitPrompt / the API open upgrade or generate. Never let the model invent
      // "the app will attach an image shortly" without calling generate.
      if (onGenerateImage && !pendingAttachment && !editingMessageId) {
        const imagePrompt =
          extractImageGenPrompt(text) ??
          extractImageRevisionPrompt(text, imageGenRevisionContext(messages));
        if (imagePrompt) {
          if (imageGenerating) return;
          setInput("");
          Keyboard.dismiss();
          onGenerateImage(imagePrompt, text);
          return;
        }
      }

      const authToken = token;
      if (!authToken) return;

      const attached = pendingAttachment;
      sendInFlightRef.current = true;
      // Clear the composer immediately — including the attachment chip.
      // Upload continues in the background; keeping the chip + attachBusy
      // showed a second spinner next to the optimistic bubble.
      setInput("");
      setPendingAttachment(null);
      setSendPhase("idle");
      Keyboard.dismiss();

      const isEdit = Boolean(editingMessageId && chatId);
      const optimisticId = `local-${Date.now()}`;
      const createdAt = new Date().toISOString();
      let addedOptimistic = false;
      if (!isEdit) {
        addedOptimistic = true;
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
      }

      const restoreDraft = () => {
        if (addedOptimistic) {
          setPendingOutboundId(null);
          setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
          newMessageCountRef.current = Math.max(0, newMessageCountRef.current - 1);
        }
        setInput(text);
        setPendingAttachment(attached);
        sendInFlightRef.current = false;
        setSendPhase("idle");
      };

      let attachmentIds: string[] | undefined;
      if (attached) {
        try {
          const id = await uploadChatAttachment(authToken, attached);
          attachmentIds = [id];
        } catch (error) {
          restoreDraft();
          feedback?.error(
            error instanceof Error ? error.message : t("chat.attach_failed"),
          );
          return;
        }
      }

      const geoResult = await resolveClientGeoForQuery(authToken, text, t, updateUser);
      if (!geoResult.ok) {
        restoreDraft();
        return;
      }
      const clientGeo = geoResult.clientGeo;

      if (editingMessageId && chatId) {
        const editId = editingMessageId;
        setEditingMessageId(null);
        void editMessage(editId, text, selectedModel, clientGeo);
        sendInFlightRef.current = false;
        setSendPhase("idle");
        return;
      }

      if (!chatId) {
        creatingRef.current = true;
        setSendPhase("creating");
        try {
          const id = await prepareDraftChat(undefined, selectedModel);
          if (!id) throw new Error("Could not create chat");
          skipLoadForChatIdRef.current = id;
          setChatTitle(null);
          setChatId(id);
          draftChatIdRef.current = null;
          setDraftChatId(null);
          router.setParams({ chatId: id });
          setPendingSend(
            buildPendingSendAfterCreate({
              text,
              attached,
              attachmentIds,
              optimisticId,
              clientGeo,
              model: selectedModel,
            }),
          );
        } catch {
          restoreDraft();
          feedback?.error(t("chat.error_generic"));
        } finally {
          creatingRef.current = false;
        }
        return;
      }
      const pending = buildPendingSendAfterCreate({
        text,
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
      streaming,
      token,
      creatingRef,
      attachBusy,
      editingMessageId,
      chatId,
      newMessageCountRef,
      editMessage,
      selectedModel,
      setMessages,
      prepareDraftChat,
      skipLoadForChatIdRef,
      draftChatIdRef,
      setDraftChatId,
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
    ],
  );

  const handlePickAttachment = useCallback(() => {
    if (!token || attachBusy || streaming) return;
    Keyboard.dismiss();
    // Let the keyboard finish dismissing before presenting the Modal so the
    // first tap isn't swallowed on Android.
    requestAnimationFrame(() => setAttachSheetOpen(true));
  }, [token, attachBusy, streaming]);

  const waitForPickerUi = useCallback(() => scheduleIdlePromise(), []);

  const handleAttachmentSheetSelect = useCallback(
    async (source: AttachmentSource) => {
      if (attachPickInFlightRef.current || !token || attachBusy || streaming) return;
      attachPickInFlightRef.current = true;
      setAttachPicking(true);
      setAttachSheetOpen(false);
      await waitForPickerUi();

      if (!token || attachBusy || streaming) {
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
          router.push({ pathname: "/gallery", params: { pick: "1" } });
          return;
        }
        const picked =
          source === "camera"
            ? await pickFromCamera()
            : source === "photo"
              ? await pickFromPhotoLibrary()
              : await pickDocument();
        if (picked) {
          setPendingAttachment(picked);
        }
      } catch (error) {
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
    [attachBusy, feedback, router, streaming, t, token, waitForPickerUi],
  );

  const handleMathScanCaptured = useCallback((pending: PendingAttachment) => {
    setPendingAttachment(pending);
    setInput(defaultMathCameraPrompt());
    setMathScannerOpen(false);
  }, []);

  const handleEditMessage = useCallback(
    (message: Message) => {
      if (streaming) return;
      const parsed = parseUserMessageContent(message.content);
      setInput(parsed.caption || message.content);
      setEditingMessageId(message.id);
      setPendingAttachment(null);
    },
    [streaming],
  );

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
    editingMessageId,
    setEditingMessageId,
    handleSend,
    handlePickAttachment,
    handleAttachmentSheetSelect,
    handleMathScanCaptured,
    handleEditMessage,
    creatingRef,
    pendingOutboundId,
  };
}
