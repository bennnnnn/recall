import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, Chat } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { useViewOwner } from "@/features/chat/hooks/useViewOwner";
import { beginChatMutation } from "@/features/chat/model/mutationLock";
import { clearCachedChatMessages } from "@/features/chat/model/messageCache";
import { getCachedChats } from "@/features/chat/model/chatListCache";
import { emitAppEvent } from "@/lib/appEvents";
import { abandonActiveChatIfDeleted } from "@/features/chat/drawer/drawer";
import { archiveBulkTargets, bulkInParts } from "@/features/chat/drawer/drawerChatSelection";
import { notifyDestructive } from "@/lib/haptics";
import type { IconName } from "@/ui/icons/names";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { confirmDialog } from "@/ui/overlay/dialogs";

/** Each edit takes every chat at once: the drawer list is copied, sorted and drawn once. */
type Params = {
  token: string | null;
  isDrawerOpen: boolean;
  insertChatsInGroups: (chats: readonly Chat[]) => void;
  patchChatsInGroups: (patches: readonly (readonly [string, Partial<Chat>])[]) => void;
  removeChatsFromGroupsById: (chatIds: readonly string[]) => void;
  reloadChats: () => void;
  showActionBanner: (message: string, icon?: IconName) => void;
};

/** Each chat as the drawer holds it now, else as it was selected. */
function snapshotsOf(targets: Chat[]): Chat[] {
  const cached = getCachedChats(targets.map((chat) => chat.id));
  return targets.map((chat) => ({ ...(cached.get(chat.id) ?? chat) }));
}

/** Multi-select bulk archive/delete for the drawer's selection mode. */
export function useChatBulkActions({
  token, isDrawerOpen, insertChatsInGroups, patchChatsInGroups, removeChatsFromGroupsById,
  reloadChats, showActionBanner,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const { owns } = useViewOwner(`${session}:${isDrawerOpen}:${signedIn}`);
  const currentSession = useCallback(() => session === getSessionGeneration(), [session]);
  const currentView = useCallback(
    () => owns() && isDrawerOpen && currentSession(),
    [isDrawerOpen, owns, currentSession],
  );

  const bulkArchiveChats = useCallback(
    (chats: Chat[], onSuccess?: () => void) => {
      const targets = archiveBulkTargets(chats).map((chat) => ({ ...chat }));
      if (!token || !currentView() || targets.length === 0) return;
      void confirmDialog({
        title: t("drawer.bulk_archive_confirm_title"),
        message: t("drawer.bulk_archive_confirm_body", { count: targets.length }),
        cancelLabel: t("common.cancel"),
        confirmLabel: t("drawer.bulk_archive"),
      }).then(async (ok) => {
        if (!ok) return;
        if (!currentView()) return;
        const release = beginChatMutation(session, targets.map((chat) => chat.id));
        if (!release) return;
        const snapshots = snapshotsOf(targets);
        try {
          patchChatsInGroups(targets.map((chat) => [chat.id, { archived: true, pinned: false }] as const));
          // One request per 200 chats: one per chat passed the REST rate limit.
          const archived = await bulkInParts(
            targets.map((chat) => chat.id),
            (part) => api.bulkChats(token, "archive", part),
          );
          if (!currentSession()) return;
          const failed = snapshots.filter((chat) => !archived.has(chat.id));
          const archivedCount = archived.size;
          // Archiving clears pins too. Restore the whole failed row, and
          // only after every sibling request has settled before reloading.
          patchChatsInGroups([
            ...targets
              .filter((chat) => archived.has(chat.id))
              .map((chat) => [chat.id, { pinned: false, archived: true }] as const),
            ...failed.map((chat) => [chat.id, chat] as const),
          ]);
          if (failed.length > 0) {
            reloadChats();
            if (currentView()) reportRecoverableError(feedback, t("chat.archive_failed"));
          } else if (currentView()) {
            if (archivedCount > 0) {
              showActionBanner(t("drawer.bulk_archived_toast", { count: archivedCount }), "archive");
            }
            onSuccess?.();
          }
        } finally { release(); }
      });
    },
    [token, currentView, t, session, currentSession, patchChatsInGroups, reloadChats, feedback, showActionBanner],
  );

  const bulkDeleteChats = useCallback(
    (chats: Chat[], onSuccess?: () => void) => {
      const targets = chats.map((chat) => ({ ...chat }));
      if (!token || !currentView() || targets.length === 0) return;
      void confirmDialog({
        title: t("drawer.bulk_delete_confirm_title"),
        message: t("drawer.bulk_delete_confirm_body", { count: targets.length }),
        cancelLabel: t("common.cancel"),
        confirmLabel: t("common.delete"),
        destructive: true,
      }).then(async (ok) => {
        if (!ok) return;
        if (!currentView()) return;
        const release = beginChatMutation(session, targets.map((chat) => chat.id));
        if (!release) return;
        const snapshots = snapshotsOf(targets);
        try {
          removeChatsFromGroupsById(targets.map((chat) => chat.id));
          const deleted = await bulkInParts(
            targets.map((chat) => chat.id),
            (part) => api.bulkChats(token, "delete", part),
          );
          if (!currentSession()) return;
          const deletedIds = snapshots.filter((chat) => deleted.has(chat.id)).map((chat) => chat.id);
          // A row a failed delete took out comes back. A deleted one stays out: the
          // `chatsDeleted` event below removes it again (useDrawerChatList), in case a read put it back.
          insertChatsInGroups(snapshots.filter((chat) => !deleted.has(chat.id)));
          for (const chatId of deletedIds) void clearCachedChatMessages(chatId);
          if (deletedIds.length > 0) {
            emitAppEvent("chatsDeleted", { chatIds: deletedIds });
            abandonActiveChatIfDeleted(deletedIds);
          }
          if (deletedIds.length !== targets.length) {
            reloadChats();
            if (currentView()) reportRecoverableError(feedback, t("chat.delete_failed"));
          } else if (currentView()) {
            notifyDestructive();
            showActionBanner(t("drawer.bulk_deleted_toast", { count: deletedIds.length }), "trash");
            onSuccess?.();
          }
        } finally { release(); }
      });
    },
    [token, currentView, t, session, removeChatsFromGroupsById, currentSession, insertChatsInGroups, reloadChats, feedback, showActionBanner],
  );

  return { bulkArchiveChats, bulkDeleteChats };
}
