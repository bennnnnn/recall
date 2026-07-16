import { useCallback } from "react";
import { Alert } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { api, Chat } from "@/lib/api";
import { clearCachedChatMessages } from "@/lib/chatMessageCache";
import { abandonActiveChatIfDeleted } from "@/lib/drawer";
import { archiveBulkTargets } from "@/lib/drawerChatSelection";

type Params = {
  token: string | null;
  insertChatInGroups: (chat: Chat) => void;
  moveChatArchiveState: (chatId: string, archived: boolean) => void;
  removeChatFromGroupsById: (chatId: string) => void;
  reloadChats: () => void;
  showActionBanner: (message: string, icon?: keyof typeof Ionicons.glyphMap) => void;
};

/** Multi-select bulk archive/delete for the drawer's selection mode. */
export function useChatBulkActions({
  token,
  insertChatInGroups,
  moveChatArchiveState,
  removeChatFromGroupsById,
  reloadChats,
  showActionBanner,
}: Params) {
  const { t } = useTranslation();

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

  return {
    bulkArchiveChats,
    bulkDeleteChats,
  };
}
