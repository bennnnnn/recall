import { useCallback, useEffect, useState } from "react";
import { Alert } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { api, Chat } from "@/lib/api";
import { clearCachedChatMessages } from "@/lib/chatMessageCache";
import {
  deletedIncludesActiveChat,
  startNewChatGlobal,
} from "@/lib/drawer";
import { archiveBulkTargets } from "@/lib/drawerChatSelection";
import { sanitizeManualChatTitle } from "@/lib/chatTitle";
import { shareConversation } from "@/lib/share";

type Params = {
  token: string | null;
  isDrawerOpen: boolean;
  patchChatInGroups: (chatId: string, patch: Partial<Chat>) => void;
  insertChatInGroups: (chat: Chat) => void;
  moveChatPinState: (chatId: string, pinned: boolean) => void;
  moveChatArchiveState: (chatId: string, archived: boolean) => void;
  removeChatFromGroupsById: (chatId: string) => void;
  reloadChats: () => void;
};

function abandonActiveChatIfDeleted(deletedIds: readonly string[]) {
  if (!deletedIncludesActiveChat(deletedIds)) return;
  startNewChatGlobal({ force: true });
}

export function useDrawerChatActions({
  token,
  isDrawerOpen,
  patchChatInGroups,
  insertChatInGroups,
  moveChatPinState,
  moveChatArchiveState,
  removeChatFromGroupsById,
  reloadChats,
}: Params) {
  const { t } = useTranslation();
  const [menuChat, setMenuChat] = useState<Chat | null>(null);
  const [renameVisible, setRenameVisible] = useState(false);
  const [renameText, setRenameText] = useState("");
  const [renameTarget, setRenameTarget] = useState<Chat | null>(null);
  const [actionBanner, setActionBanner] = useState<{
    message: string;
    icon?: keyof typeof Ionicons.glyphMap;
  } | null>(null);

  useEffect(() => {
    if (!isDrawerOpen) setMenuChat(null);
  }, [isDrawerOpen]);

  const showActionBanner = useCallback(
    (message: string, icon?: keyof typeof Ionicons.glyphMap) => {
      setActionBanner({ message, icon });
    },
    [],
  );

  const dismissActionBanner = useCallback(() => setActionBanner(null), []);

  const closeMenu = useCallback(() => setMenuChat(null), []);

  const showRowMenu = useCallback((chat: Chat) => {
    setMenuChat(chat);
  }, []);

  const handleShareChat = useCallback(async () => {
    if (!token || !menuChat) return;
    const chat = menuChat;
    closeMenu();
    try {
      const msgs = await api.listAllMessages(token, chat.id);
      await shareConversation(chat.title, msgs);
    } catch {
      Alert.alert(t("common.error"), t("chat.share_failed"));
    }
  }, [token, menuChat, closeMenu, t]);

  const openRenameFromMenu = useCallback(() => {
    if (!menuChat) return;
    setRenameTarget(menuChat);
    setRenameText(menuChat.title ?? "");
    closeMenu();
    setRenameVisible(true);
  }, [menuChat, closeMenu]);

  const confirmRename = useCallback(async () => {
    const title = sanitizeManualChatTitle(renameText);
    if (!title || !renameTarget || !token) {
      setRenameVisible(false);
      return;
    }
    const prevTitle = renameTarget.title;
    patchChatInGroups(renameTarget.id, { title });
    setRenameVisible(false);
    setRenameTarget(null);
    try {
      await api.renameChat(token, renameTarget.id, title);
      showActionBanner(t("chat.renamed_toast"), "pencil-outline");
    } catch {
      patchChatInGroups(renameTarget.id, { title: prevTitle ?? null });
      Alert.alert(t("common.error"), t("chat.rename_failed"));
    }
  }, [renameText, renameTarget, token, patchChatInGroups, showActionBanner, t]);

  const togglePinChat = useCallback(async () => {
    if (!token || !menuChat) return;
    const chat = menuChat;
    const next = !chat.pinned;
    closeMenu();
    moveChatPinState(chat.id, next);
    try {
      await api.setPin(token, chat.id, next);
      showActionBanner(
        next ? t("chat.pinned_toast") : t("chat.unpinned_toast"),
        next ? "bookmark" : "bookmark-outline",
      );
    } catch {
      moveChatPinState(chat.id, !next);
      Alert.alert(t("common.error"), t("chat.pin_failed"));
    }
  }, [token, menuChat, closeMenu, moveChatPinState, showActionBanner, t]);

  const toggleArchiveChat = useCallback(async () => {
    if (!token || !menuChat) return;
    const chat = menuChat;
    const next = !chat.archived;
    closeMenu();
    moveChatArchiveState(chat.id, next);
    try {
      await api.setArchive(token, chat.id, next);
      showActionBanner(
        next ? t("chat.archived_toast") : t("chat.unarchived_toast"),
        next ? "archive-outline" : "arrow-undo-outline",
      );
    } catch {
      moveChatArchiveState(chat.id, !next);
      Alert.alert(t("common.error"), t("common.error"));
    }
  }, [token, menuChat, closeMenu, moveChatArchiveState, showActionBanner, t]);

  const requestDeleteChat = useCallback(
    (chat: Chat) => {
      Alert.alert(t("chat.delete_confirm_title"), t("chat.delete_confirm_body"), [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("common.delete"),
          style: "destructive",
          onPress: async () => {
            if (!token) return;
            removeChatFromGroupsById(chat.id);
            try {
              await api.deleteChat(token, chat.id);
              void clearCachedChatMessages(chat.id);
              abandonActiveChatIfDeleted([chat.id]);
              showActionBanner(t("chat.deleted_toast"), "trash-outline");
            } catch {
              insertChatInGroups(chat);
              Alert.alert(t("common.error"), t("chat.delete_failed"));
            }
          },
        },
      ]);
    },
    [token, removeChatFromGroupsById, insertChatInGroups, showActionBanner, t],
  );

  const bulkArchiveChats = useCallback(
    (chats: Chat[], onSuccess?: () => void) => {
      const targets = archiveBulkTargets(chats);
      if (targets.length === 0) return;
      Alert.alert(
        t("drawer.bulk_archive_confirm_title"),
        t("drawer.bulk_archive_confirm_body", { count: targets.length }),
        [
          { text: t("common.cancel"), style: "cancel" },
          {
            text: t("drawer.bulk_archive"),
            onPress: async () => {
              if (!token) return;
              const snapshots = targets.map((chat) => ({ ...chat }));
              for (const chat of targets) {
                moveChatArchiveState(chat.id, true);
              }
              try {
                await Promise.all(
                  targets.map((chat) => api.setArchive(token, chat.id, true)),
                );
                showActionBanner(
                  t("drawer.bulk_archived_toast", { count: targets.length }),
                  "archive-outline",
                );
                onSuccess?.();
              } catch {
                for (const chat of snapshots) {
                  moveChatArchiveState(chat.id, Boolean(chat.archived));
                }
                reloadChats();
                Alert.alert(t("common.error"), t("chat.archive_failed"));
              }
            },
          },
        ],
      );
    },
    [token, moveChatArchiveState, showActionBanner, reloadChats, t],
  );

  const bulkDeleteChats = useCallback(
    (chats: Chat[], onSuccess?: () => void) => {
      if (chats.length === 0) return;
      Alert.alert(
        t("drawer.bulk_delete_confirm_title"),
        t("drawer.bulk_delete_confirm_body", { count: chats.length }),
        [
          { text: t("common.cancel"), style: "cancel" },
          {
            text: t("common.delete"),
            style: "destructive",
            onPress: async () => {
              if (!token) return;
              const snapshots = chats.map((chat) => ({ ...chat }));
              const deletedIds = chats.map((chat) => chat.id);
              for (const chat of chats) {
                removeChatFromGroupsById(chat.id);
              }
              const results = await Promise.allSettled(
                chats.map((chat) => api.deleteChat(token, chat.id)),
              );
              const failed = results.filter((r) => r.status === "rejected").length;
              if (failed === 0) {
                for (const id of deletedIds) {
                  void clearCachedChatMessages(id);
                }
                abandonActiveChatIfDeleted(deletedIds);
                showActionBanner(
                  t("drawer.bulk_deleted_toast", { count: chats.length }),
                  "trash-outline",
                );
                onSuccess?.();
                return;
              }
              for (const chat of snapshots) {
                insertChatInGroups(chat);
              }
              reloadChats();
              Alert.alert(t("common.error"), t("chat.delete_failed"));
            },
          },
        ],
      );
    },
    [token, removeChatFromGroupsById, insertChatInGroups, showActionBanner, reloadChats, t],
  );

  const confirmDeleteChat = useCallback(() => {
    if (!menuChat) return;
    const chat = menuChat;
    closeMenu();
    requestDeleteChat(chat);
  }, [menuChat, closeMenu, requestDeleteChat]);

  const closeRename = useCallback(() => {
    setRenameVisible(false);
    setRenameTarget(null);
  }, []);

  return {
    menuChat,
    renameVisible,
    renameText,
    setRenameText,
    actionBanner,
    dismissActionBanner,
    closeMenu,
    showRowMenu,
    handleShareChat,
    openRenameFromMenu,
    confirmRename,
    togglePinChat,
    toggleArchiveChat,
    confirmDeleteChat,
    requestDeleteChat,
    bulkArchiveChats,
    bulkDeleteChats,
    closeRename,
  };
}
