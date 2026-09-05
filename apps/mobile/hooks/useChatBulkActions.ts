import { useCallback, useEffect, useRef } from "react";
import { Alert } from "react-native";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, Chat } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { beginChatMutation } from "@/lib/chat/chatMutationLock";
import { clearCachedChatMessages } from "@/lib/chatMessageCache";
import { getCachedChat } from "@/lib/cache/chatListCache";
import { invalidateGalleryCache } from "@/lib/cache/galleryListCache";
import { abandonActiveChatIfDeleted } from "@/lib/drawer";
import { archiveBulkTargets } from "@/lib/drawerChatSelection";
import { type IoniconName } from "@/lib/icons";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

type Params = {
  token: string | null;
  isDrawerOpen: boolean;
  insertChatInGroups: (chat: Chat) => void;
  patchChatInGroups: (chatId: string, patch: Partial<Chat>) => void;
  moveChatArchiveState: (chatId: string, archived: boolean) => void;
  removeChatFromGroupsById: (chatId: string) => void;
  reloadChats: () => void;
  showActionBanner: (message: string, icon?: IoniconName) => void;
};

/** Multi-select bulk archive/delete for the drawer's selection mode. */
export function useChatBulkActions({
  token, isDrawerOpen, insertChatInGroups, patchChatInGroups, moveChatArchiveState,
  removeChatFromGroupsById, reloadChats, showActionBanner,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const viewRef = useRef({ session, isDrawerOpen, signedIn });
  if (viewRef.current.session !== session || viewRef.current.isDrawerOpen !== isDrawerOpen || viewRef.current.signedIn !== signedIn) {
    viewRef.current = { session, isDrawerOpen, signedIn };
  }
  const view = viewRef.current;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const currentSession = useCallback(() => session === getSessionGeneration(), [session]);
  const currentView = useCallback(
    () => mounted.current && isDrawerOpen && viewRef.current === view && currentSession(),
    [isDrawerOpen, view, currentSession],
  );

  const bulkArchiveChats = useCallback(
    (chats: Chat[], onSuccess?: () => void) => {
      const targets = archiveBulkTargets(chats).map((chat) => ({ ...chat }));
      if (!token || !currentView() || targets.length === 0) return;
      Alert.alert(
        t("drawer.bulk_archive_confirm_title"),
        t("drawer.bulk_archive_confirm_body", { count: targets.length }),
        [
          { text: t("common.cancel"), style: "cancel" },
          {
            text: t("drawer.bulk_archive"),
            onPress: async () => {
              if (!currentView()) return;
              const release = beginChatMutation(session, targets.map((chat) => chat.id));
              if (!release) return;
              const snapshots = targets.map((chat) => ({ ...(getCachedChat(chat.id) ?? chat) }));
              try {
                for (const chat of targets) moveChatArchiveState(chat.id, true);
                const results = await Promise.allSettled(
                  targets.map((chat) => api.setArchive(token, chat.id, true)),
                );
                if (!currentSession()) return;
                const failed = snapshots.filter((_chat, index) => results[index].status === "rejected");
                let archivedCount = 0;
                for (const [index, result] of results.entries()) {
                  if (result.status !== "fulfilled") continue;
                  const saved = result.value;
                  patchChatInGroups(targets[index].id, { pinned: saved.pinned, archived: Boolean(saved.archived) });
                  if (saved.archived) archivedCount++;
                }
                // Archiving clears pins too. Restore the whole failed row, and
                // only after every sibling request has settled before reloading.
                for (const chat of failed) patchChatInGroups(chat.id, chat);
                if (failed.length > 0) {
                  reloadChats();
                  if (currentView()) reportRecoverableError(feedback, t("chat.archive_failed"));
                } else if (currentView()) {
                  if (archivedCount > 0) {
                    showActionBanner(t("drawer.bulk_archived_toast", { count: archivedCount }), "archive-outline");
                  }
                  onSuccess?.();
                }
              } finally { release(); }
            },
          },
        ],
      );
    },
    [token, currentView, t, session, moveChatArchiveState, currentSession, patchChatInGroups, reloadChats, feedback, showActionBanner],
  );

  const bulkDeleteChats = useCallback(
    (chats: Chat[], onSuccess?: () => void) => {
      const targets = chats.map((chat) => ({ ...chat }));
      if (!token || !currentView() || targets.length === 0) return;
      Alert.alert(
        t("drawer.bulk_delete_confirm_title"),
        t("drawer.bulk_delete_confirm_body", { count: targets.length }),
        [
          { text: t("common.cancel"), style: "cancel" },
          {
            text: t("common.delete"),
            style: "destructive",
            onPress: async () => {
              if (!currentView()) return;
              const release = beginChatMutation(session, targets.map((chat) => chat.id));
              if (!release) return;
              const snapshots = targets.map((chat) => ({ ...(getCachedChat(chat.id) ?? chat) }));
              try {
                for (const chat of targets) removeChatFromGroupsById(chat.id);
                const results = await Promise.allSettled(
                  targets.map((chat) => api.deleteChat(token, chat.id)),
                );
                if (!currentSession()) return;
                const deletedIds: string[] = [];
                for (const [index, result] of results.entries()) {
                  const chat = snapshots[index];
                  if (result.status === "rejected") insertChatInGroups(chat);
                  else {
                    removeChatFromGroupsById(chat.id);
                    deletedIds.push(chat.id);
                    void clearCachedChatMessages(chat.id);
                  }
                }
                if (deletedIds.length > 0) {
                  invalidateGalleryCache();
                  abandonActiveChatIfDeleted(deletedIds);
                }
                if (deletedIds.length !== targets.length) {
                  reloadChats();
                  if (currentView()) reportRecoverableError(feedback, t("chat.delete_failed"));
                } else if (currentView()) {
                  showActionBanner(t("drawer.bulk_deleted_toast", { count: deletedIds.length }), "trash-outline");
                  onSuccess?.();
                }
              } finally { release(); }
            },
          },
        ],
      );
    },
    [token, currentView, t, session, removeChatFromGroupsById, currentSession, insertChatInGroups, reloadChats, feedback, showActionBanner],
  );

  return { bulkArchiveChats, bulkDeleteChats };
}
