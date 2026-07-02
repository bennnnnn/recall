import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, InteractionManager, Keyboard } from "react-native";
import { useRouter } from "expo-router";

type Router = ReturnType<typeof useRouter>;

import type { AttachmentSource } from "@/components/AttachmentSourceSheet";
import type { useDraftChat } from "@/hooks/useDraftChat";
import type { useChatScroll } from "@/hooks/useChatScroll";
import { type Message } from "@/lib/api";
import { tap } from "@/lib/haptics";
import { parseUserMessageContent } from "@/lib/messageAttachments";
import {
  buildOptimisticUserMessage,
  buildPendingSendAfterCreate,
  shouldBlockSend,
} from "@/lib/chatSendLogic";
import { confirmGeoLocationAccess } from "@/lib/confirmGeoLocation";
import type { ClientGeo } from "@/lib/clientGeo";
import { ensureNearbyLocation } from "@/lib/ensureNearbyLocation";
import { isAmbiguousLocalPlacesQuery, isGeoQuery } from "@/lib/localPlacesQuery";
import {
  pickDocument,
  pickFromCamera,
  pickFromPhotoLibrary,
  uploadChatAttachment,
  messageTextForSend,
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
  mergeUser: (patch: Partial<import("@/lib/api").User>) => void;
  t: (key: string) => string;
  onStreamBusy?: () => void;
  isOffline: boolean;
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
  mergeUser,
  t,
  onStreamBusy,
  isOffline,
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
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [pendingOutboundId, setPendingOutboundId] = useState<string | null>(null);
  const [pendingSend, setPendingSend] = useState<{
    text: string;
    skipUserBubble?: boolean;
    trackSendingMessageId?: string;
    attachmentIds?: string[];
    localImageUri?: string | null;
    clientGeo?: ClientGeo | null;
    model: string;
  } | null>(null);

  const attachPickInFlightRef = useRef(false);

  useEffect(() => {
    if (chatId && pendingSend) {
      const {
        text,
        skipUserBubble,
        trackSendingMessageId,
        attachmentIds,
        localImageUri,
        clientGeo,
        model,
      } = pendingSend;
      setPendingSend(null);
      sendMessage(text, {
        skipUserBubble,
        trackSendingMessageId,
        attachmentIds,
        localImageUri,
        model,
        clientGeo,
      });
    }
  }, [chatId, pendingSend, sendMessage]);

  const handleSend = useCallback(
    async (overrideText?: string) => {
      const text = (overrideText ?? input).trim();
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

      const authToken = token;
      if (!authToken) return;

      let attachmentIds: string[] | undefined;
      const attached = pendingAttachment;
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
          return;
        }
        setAttachBusy(false);
        setPendingAttachment(null);
      }

      setInput("");
      newMessageCountRef.current += 1;

      let clientGeo: ClientGeo | null = null;
      if (isGeoQuery(text) && !isAmbiguousLocalPlacesQuery(text)) {
        const allowed = await confirmGeoLocationAccess(t);
        if (!allowed) {
          setInput(text);
          return;
        }
        clientGeo = await ensureNearbyLocation(authToken, text);
        if (!clientGeo) {
          setInput(text);
          Alert.alert(t("chat.location_required_title"), t("chat.location_required_body"));
          return;
        }
        mergeUser({ location: clientGeo.label, location_enabled: true });
      }

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
        } finally {
          creatingRef.current = false;
        }
        return;
      }
      newMessageCountRef.current += 1;
      sendMessage(messageTextForSend(text, attached), {
        attachmentIds,
        localImageUri: attached?.kind === "image" ? attached.localUri : null,
        model: selectedModel,
        clientGeo,
      });
    },
    [
      input,
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
      mergeUser,
      t,
      onStreamBusy,
      isOffline,
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
    setAttachSheetOpen(true);
  }, [token, attachBusy, streaming]);

  const waitForPickerUi = useCallback(
    () =>
      new Promise<void>((resolve) => {
        InteractionManager.runAfterInteractions(() => {
          requestAnimationFrame(() => {
            requestAnimationFrame(() => resolve());
          });
        });
      }),
    [],
  );

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
        const picked =
          source === "camera"
            ? await pickFromCamera()
            : source === "photo"
              ? await pickFromPhotoLibrary()
              : await pickDocument();
        if (picked) setPendingAttachment(picked);
      } catch (error) {
        Alert.alert(
          t("chat.attach_failed"),
          error instanceof Error ? error.message : t("common.error"),
        );
      } finally {
        attachPickInFlightRef.current = false;
      }
    },
    [attachBusy, streaming, t, token, waitForPickerUi],
  );

  const handleQuizAnswer = useCallback(
    (_messageId: string, letter: "A" | "B" | "C" | "D") => {
      if (streaming || creatingRef.current) return;
      void handleSend(letter);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [streaming, chatId],
  );

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
    editingMessageId,
    setEditingMessageId,
    handleSend,
    handlePickAttachment,
    handleAttachmentSheetSelect,
    handleQuizAnswer,
    handleEditMessage,
    creatingRef,
    pendingOutboundId,
  };
}
