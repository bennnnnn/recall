import { useCallback, useState } from "react";
import { Alert } from "react-native";
import { useRouter } from "expo-router";
import type { Ionicons } from "@expo/vector-icons";

type Router = ReturnType<typeof useRouter>;

import { moveChatArchiveGlobal, patchChatGlobal } from "@/lib/drawer";
import { api, type Message } from "@/lib/api";
import { tap } from "@/lib/haptics";
import { shareConversation } from "@/lib/share";
import { sanitizeManualChatTitle } from "@/lib/chatTitle";

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
    icon?: keyof typeof Ionicons.glyphMap;
  } | null>(null);

  const showActionBanner = useCallback(
    (message: string, icon?: keyof typeof Ionicons.glyphMap) => {
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

  const handleShare = useCallback(async () => {
    if (!token || !chatId) {
      await shareConversation(chatTitle, messages);
      return;
    }
    try {
      const all = await api.listAllMessages(token, chatId);
      await shareConversation(chatTitle, all);
    } catch {
      await shareConversation(chatTitle, messages);
    }
  }, [token, chatId, chatTitle, messages]);

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
    try {
      const u = await api.renameChat(token, chatId, title);
      setChatTitle(u.title);
      patchChatGlobal(chatId, { title: u.title });
      showActionBanner(t("chat.renamed_toast"), "pencil-outline");
    } catch {
      Alert.alert(t("common.error"), t("chat.rename_failed"));
    }
    setRenameVisible(false);
  }, [renameText, chatId, token, setChatTitle, showActionBanner, t]);

  const togglePin = useCallback(async () => {
    if (!chatId || !token) return;
    tap();
    const next = !pinned;
    setPinned(next);
    try {
      await api.setPin(token, chatId, next);
      showActionBanner(
        next ? t("chat.pinned_toast") : t("chat.unpinned_toast"),
        next ? "bookmark" : "bookmark-outline",
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
            try {
              await api.deleteChat(token, chatId);
              showActionBanner(t("chat.deleted_toast"), "trash-outline");
              setTimeout(() => {
                if (router.canGoBack()) {
                  router.back();
                } else {
                  router.replace("/");
                }
              }, 700);
            } catch {
              Alert.alert(t("common.error"), t("chat.delete_failed"));
            }
          },
        },
      ],
    );
  }, [chatId, token, router, showActionBanner, t]);

  const onShareFromMenu = useCallback(() => {
    tap();
    closeMenu();
    void handleShare();
  }, [closeMenu, handleShare]);

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
    openRename,
    confirmRename,
    togglePin,
    toggleArchive,
    confirmDelete,
    onShareFromMenu,
    onRenameFromMenu,
    onTogglePinFromMenu,
    onToggleArchiveFromMenu,
    onDeleteFromMenu,
  };
}
