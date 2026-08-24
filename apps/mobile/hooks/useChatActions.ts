import { useCallback, useState } from "react";
import { Alert } from "react-native";
import { useRouter } from "expo-router";

import { type IoniconName } from "@/lib/icons";

type Router = ReturnType<typeof useRouter>;

import { insertChatGlobal, moveChatArchiveGlobal, patchChatGlobal, removeChatGlobal } from "@/lib/drawer";
import { api, type Chat, type Message } from "@/lib/api";
import { FREE_CHAT_MODEL_ID } from "@/lib/modelCatalogFallback";
import { clearCachedChatMessages } from "@/lib/chatMessageCache";
import { exportConversationAsPdf } from "@/lib/exportMessagePdf";
import { isShareCancelled } from "@/lib/exportPdf";
import { tap } from "@/lib/haptics";
import { shareConversation } from "@/lib/share";
import { sanitizeManualChatTitle } from "@/lib/chat/chatTitle";

const SERVER_MESSAGE_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type Options = {
  token: string | null;
  chatId: string | null;
  chatTitle: string | null;
  messages: Message[];
  pinned: boolean;
  setPinned: React.Dispatch<React.SetStateAction<boolean>>;
  archived: boolean;
  setArchived: React.Dispatch<React.SetStateAction<boolean>>;
  setChatTitle: React.Dispatch<React.SetStateAction<string | null>>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  router: Router;
  t: (key: string, options?: Record<string, unknown>) => string;
};

export function useChatActions({
  token,
  chatId,
  chatTitle,
  messages,
  pinned,
  setPinned,
  archived,
  setArchived,
  setChatTitle,
  setMessages,
  router,
  t,
}: Options) {
  const [menuVisible, setMenuVisible] = useState(false);
  const [renameVisible, setRenameVisible] = useState(false);
  const [renameText, setRenameText] = useState("");
  const [actionBanner, setActionBanner] = useState<{
    message: string;
    icon?: IoniconName;
  } | null>(null);

  const showActionBanner = useCallback(
    (message: string, icon?: IoniconName) => {
      setActionBanner({ message, icon });
    },
    [],
  );

  const dismissActionBanner = useCallback(() => setActionBanner(null), []);

  const closeMenu = useCallback(() => setMenuVisible(false), []);

  const handleFeedback = useCallback(
    (messageId: string, next: "up" | "down" | null) => {
      let previous: "up" | "down" | null = null;
      setMessages((prev) =>
        prev.map((mm) => {
          if (mm.id !== messageId) return mm;
          previous = mm.feedback ?? null;
          return { ...mm, feedback: next };
        }),
      );
      if (token && chatId && SERVER_MESSAGE_ID.test(messageId)) {
        void api.setMessageFeedback(token, chatId, messageId, next).catch(() => {
          setMessages((prev) =>
            prev.map((mm) =>
              mm.id === messageId ? { ...mm, feedback: previous } : mm,
            ),
          );
          Alert.alert(t("common.error"), t("chat.feedback_failed"));
        });
      }
    },
    [token, chatId, setMessages, t],
  );

  const loadTranscriptMessages = useCallback(async () => {
    if (!token || !chatId) return messages;
    try {
      return await api.listAllMessages(token, chatId);
    } catch {
      return messages;
    }
  }, [token, chatId, messages]);

  const handleShare = useCallback(async () => {
    showActionBanner(t("chat.status.preparing"), "share-outline");
    const transcript = await loadTranscriptMessages();
    dismissActionBanner();
    await shareConversation(chatTitle, transcript);
  }, [chatTitle, dismissActionBanner, loadTranscriptMessages, showActionBanner, t]);

  const handleExportPdf = useCallback(async () => {
    showActionBanner(t("chat.status.preparing"), "document-text-outline");
    try {
      const transcript = await loadTranscriptMessages();
      dismissActionBanner();
      await exportConversationAsPdf(chatTitle, transcript);
    } catch (error) {
      dismissActionBanner();
      if (isShareCancelled(error)) return;
      Alert.alert(t("common.error"), t("chat.export_pdf_failed"));
    }
  }, [chatTitle, dismissActionBanner, loadTranscriptMessages, showActionBanner, t]);

  const openRename = useCallback(() => {
    setRenameText(chatTitle ?? "");
    setRenameVisible(true);
  }, [chatTitle]);

  const confirmRename = useCallback(async () => {
    const title = sanitizeManualChatTitle(renameText);
    if (!title || !chatId || !token) {
      setRenameVisible(false);
      return;
    }
    const prevTitle = chatTitle;
    setChatTitle(title);
    patchChatGlobal(chatId, { title });
    setRenameVisible(false);
    try {
      const u = await api.renameChat(token, chatId, title);
      setChatTitle(u.title);
      patchChatGlobal(chatId, { title: u.title });
      showActionBanner(t("chat.renamed_toast"), "pencil-outline");
    } catch {
      setChatTitle(prevTitle);
      patchChatGlobal(chatId, { title: prevTitle });
      Alert.alert(t("common.error"), t("chat.rename_failed"));
    }
  }, [renameText, chatId, chatTitle, token, setChatTitle, showActionBanner, t]);

  const togglePin = useCallback(async () => {
    if (!chatId || !token) return;
    tap();
    const next = !pinned;
    setPinned(next);
    try {
      await api.setPin(token, chatId, next);
      showActionBanner(
        next ? t("chat.pinned_toast") : t("chat.unpinned_toast"),
        next ? "pin" : "pin-outline",
      );
    } catch {
      setPinned(!next);
      Alert.alert(t("common.error"), t("chat.pin_failed"));
    }
  }, [chatId, token, pinned, setPinned, showActionBanner, t]);

  const toggleArchive = useCallback(async () => {
    if (!chatId || !token) return;
    tap();
    const next = !archived;
    setArchived(next);
    moveChatArchiveGlobal(chatId, next);
    try {
      await api.setArchive(token, chatId, next);
      showActionBanner(
        next ? t("chat.archived_toast") : t("chat.unarchived_toast"),
        next ? "archive-outline" : "arrow-undo-outline",
      );
    } catch {
      setArchived(!next);
      moveChatArchiveGlobal(chatId, !next);
      Alert.alert(t("common.error"), t("chat.archive_failed"));
    }
  }, [chatId, token, archived, setArchived, showActionBanner, t]);

  const confirmDelete = useCallback(() => {
    Alert.alert(
      t("chat.delete_confirm_title"),
      t("chat.delete_confirm_body"),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("common.delete"),
          style: "destructive",
          onPress: async () => {
            if (!chatId || !token) return;
            const snapshot: Chat = {
              id: chatId,
              title: chatTitle,
              model:
                [...messages].reverse().find((m) => m.model)?.model ??
                FREE_CHAT_MODEL_ID,
              pinned,
              archived,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            };
            removeChatGlobal(chatId);
            try {
              await api.deleteChat(token, chatId);
              void clearCachedChatMessages(chatId);
              showActionBanner(t("chat.deleted_toast"), "trash-outline");
              setTimeout(() => {
                if (router.canGoBack()) {
                  router.back();
                } else {
                  router.replace("/");
                }
              }, 700);
            } catch {
              insertChatGlobal(snapshot);
              Alert.alert(t("common.error"), t("chat.delete_failed"));
            }
          },
        },
      ],
    );
  }, [archived, chatId, chatTitle, messages, pinned, token, router, showActionBanner, t]);

  const onShareFromMenu = useCallback(() => {
    tap();
    closeMenu();
    void handleShare();
  }, [closeMenu, handleShare]);

  const onExportPdfFromMenu = useCallback(() => {
    tap();
    closeMenu();
    void handleExportPdf();
  }, [closeMenu, handleExportPdf]);

  const onRenameFromMenu = useCallback(() => {
    tap();
    closeMenu();
    openRename();
  }, [closeMenu, openRename]);

  const onTogglePinFromMenu = useCallback(() => {
    tap();
    closeMenu();
    void togglePin();
  }, [closeMenu, togglePin]);

  const onToggleArchiveFromMenu = useCallback(() => {
    tap();
    closeMenu();
    void toggleArchive();
  }, [closeMenu, toggleArchive]);

  const onDeleteFromMenu = useCallback(() => {
    tap();
    closeMenu();
    confirmDelete();
  }, [closeMenu, confirmDelete]);

  return {
    menuVisible,
    setMenuVisible,
    renameVisible,
    renameText,
    setRenameText,
    setRenameVisible,
    actionBanner,
    showActionBanner,
    dismissActionBanner,
    closeMenu,
    handleFeedback,
    handleShare,
    handleExportPdf,
    openRename,
    confirmRename,
    togglePin,
    toggleArchive,
    confirmDelete,
    onShareFromMenu,
    onExportPdfFromMenu,
    onRenameFromMenu,
    onTogglePinFromMenu,
    onToggleArchiveFromMenu,
    onDeleteFromMenu,
  };
}
