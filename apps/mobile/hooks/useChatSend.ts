import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Keyboard } from "react-native";
import { useRouter } from "expo-router";

type Router = ReturnType<typeof useRouter>;

import type { AttachmentSource } from "@/components/AttachmentSourceSheet";
import type { useDraftChat } from "@/hooks/useDraftChat";
import type { useChatScroll } from "@/hooks/useChatScroll";
import type { Message } from "@/lib/api";
import { tap } from "@/lib/haptics";
import { parseUserMessageContent } from "@/lib/messageAttachments";
import {
  buildOptimisticUserMessage,
  buildPendingSendAfterCreate,
  shouldBlockSend,
} from "@/lib/chatSendLogic";
import { extractImageGenPrompt } from "@/lib/imageGenIntent";
import { scheduleIdlePromise } from "@/lib/scheduleIdle";
import type { ClientGeo } from "@/lib/clientGeo";
import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";
import {
  pickDocument,
  HeicUnsupportedError,
  pickFromCamera,
  pickFromPhotoLibrary,
  uploadChatAttachment,
  messageTextForSend,
  defaultMathCameraPrompt,
  type PendingAttachment,
} from "@/lib/attachments";

type DraftChat = ReturnType<typeof useDraftChat>;
type ChatScroll = ReturnType<typeof useChatScroll>;

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
  selectedModel: string;
  pendingLaunch: string | null;
  setPendingLaunch: React.Dispatch<React.SetStateAction<string | null>>;
  pendingLaunchRef: React.MutableRefObject<string | null>;
  user: import("@/lib/api").User | null;
  updateUser: (patch: Partial<import("@/lib/api").User>) => Promise<void>;
  t: (key: string) => string;
  onStreamBusy?: () => void;
  isOffline: boolean;
  resolveQuizProjectId?: () => string | null;
  onBeforeSend?: (text: string) => boolean | void;
  /** Pro-only: open the image-gen confirmation sheet for detected image-intent text. */
  onOpenImageGen?: (prompt: string) => void;
  isPro?: boolean;
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
  selectedModel,
  pendingLaunch,
  setPendingLaunch,
  pendingLaunchRef,
  user,
  updateUser,
  t,
  onStreamBusy,
  isOffline,
  resolveQuizProjectId,
  onBeforeSend,
  onOpenImageGen,
  isPro = false,
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

  const [input, setInput] = useState("");
  const [pendingAttachment, setPendingAttachment] = useState<PendingAttachment | null>(null);
  const [attachBusy, setAttachBusy] = useState(false);
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
  // Read composer text via ref so handleSend (and quiz/starter wrappers that
  // depend on it) stay identity-stable across keystrokes. Otherwise every
  // character rebuilds onQuizAnswer → sharedRowProps → renderItem and defeats
  // FlashList / ChatMessageList memo while typing.
  const inputRef = useRef(input);
  inputRef.current = input;

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
    }
  }, [chatId, pendingSend, sendMessage]);

  const handleSend = useCallback(
    async (overrideText?: string) => {
      const text = (overrideText ?? inputRef.current).trim();
      if (isOffline) {
        Alert.alert(t("chat.offline_title"), t("chat.offline_body"));
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
        Alert.alert(t("chat.error_title"), t("chat.edit_no_attachments"));
        return;
      }
      tap();
      if (onBeforeSend?.(text) === true) return;

      // Pro: route clear image-gen intent to the confirmation sheet (no LLM upsell).
      // Free users fall through so the model can mention Pro (plan is in the prompt).
      if (isPro && onOpenImageGen && !pendingAttachment && !editingMessageId) {
        const imagePrompt = extractImageGenPrompt(text);
        if (imagePrompt) {
          if (imageGenerating) return;
          setInput("");
          Keyboard.dismiss();
          onOpenImageGen(imagePrompt);
          return;
        }
      }

      const authToken = token;
      if (!authToken) return;

      const attached = pendingAttachment;
      // Leave the composer immediately — upload happens before the network
      // send, but the user should see the bubble, not a spinning preview.
      setInput("");
      setPendingAttachment(null);
      Keyboard.dismiss();

      let attachmentIds: string[] | undefined;
      if (attached) {
        setAttachBusy(true);
        try {
          const id = await uploadChatAttachment(authToken, attached);
          attachmentIds = [id];
        } catch (error) {
          Alert.alert(
            t("chat.error_title"),
            error instanceof Error ? error.message : t("common.error"),
          );
          setAttachBusy(false);
          setInput(text);
          setPendingAttachment(attached);
          return;
        }
        setAttachBusy(false);
      }

      newMessageCountRef.current += 1;

      let clientGeo: ClientGeo | null = null;
      const geoResult = await resolveClientGeoForQuery(
        authToken,
        text,
        t,
        updateUser,
        user?.location_enabled ?? false,
      );
      if (!geoResult.ok) {
        setInput(text);
        setPendingAttachment(attached);
        return;
      }
      clientGeo = geoResult.clientGeo;

      if (editingMessageId && chatId) {
        const editId = editingMessageId;
        setEditingMessageId(null);
        void editMessage(editId, text, selectedModel, clientGeo);
        return;
      }

      if (!chatId) {
        creatingRef.current = true;
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
          setPendingOutboundId(null);
        } catch {
          setPendingOutboundId(null);
          setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
          setInput(text);
          setPendingAttachment(attached);
        } finally {
          creatingRef.current = false;
        }
        return;
      }
      newMessageCountRef.current += 1;
      sendMessage(messageTextForSend(text, attached), {
        attachmentIds,
        localImageUri: attached?.kind === "image" ? attached.localUri : null,
        localFileUri: attached?.kind === "file" ? attached.localUri : null,
        localFileName: attached?.kind === "file" ? attached.fileName : null,
        localFileContentType: attached?.kind === "file" ? attached.contentType : null,
        model: selectedModel,
        clientGeo,
      });
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
      user,
      user?.location_enabled,
      updateUser,
      t,
      onStreamBusy,
      isOffline,
      onBeforeSend,
      onOpenImageGen,
      isPro,
      imageGenerating,
      setChatId,
      setChatTitle,
    ],
  );

  useEffect(() => {
    if (!pendingLaunch || chatId || streaming || creatingRef.current) return;
    const text = pendingLaunchRef.current ?? pendingLaunch;
    pendingLaunchRef.current = null;
    setPendingLaunch(null);
    void handleSend(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingLaunch, chatId, streaming]);

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
      setAttachSheetOpen(false);
      await waitForPickerUi();

      if (!token || attachBusy || streaming) {
        attachPickInFlightRef.current = false;
        return;
      }

      try {
        if (source === "solve_math_camera") {
          setMathScannerOpen(true);
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
          Alert.alert(t("chat.heic_unsupported_title"), t("chat.heic_unsupported_body"));
        } else {
          Alert.alert(
            t("chat.attach_failed"),
            error instanceof Error ? error.message : t("common.error"),
          );
        }
      } finally {
        attachPickInFlightRef.current = false;
      }
    },
    [attachBusy, streaming, t, token, waitForPickerUi],
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
    input,
    setInput,
    pendingAttachment,
    setPendingAttachment,
    attachBusy,
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
