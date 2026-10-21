import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, Chat } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { useLatestRef } from "@/lib/latestRef";
import { useViewOwner } from "@/lib/viewOwner";
import { clearCachedChatMessages } from "@/features/chat/model/messageCache";
import { getCachedChat } from "@/features/chat/model/chatListCache";
import { emitAppEvent } from "@/lib/appEvents";
import { abandonActiveChatIfDeleted } from "@/features/chat/drawer/drawer";
import type { IconName } from "@/ui/icons/names";
import { beginChatMutation } from "@/features/chat/model/mutationLock";
import { sanitizeManualChatTitle } from "@/features/chat/model/title";
import { notifyDestructive } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { confirmDialog } from "@/ui/overlay/dialogs";

type Params = {
  token: string | null;
  isDrawerOpen: boolean;
  patchChatInGroups: (chatId: string, patch: Partial<Chat>) => void;
  insertChatInGroups: (chat: Chat) => void;
  moveChatPinState: (chatId: string, pinned: boolean) => void;
  moveChatArchiveState: (chatId: string, archived: boolean) => void;
  removeChatFromGroupsById: (chatId: string) => void;
};

/** Row-menu, rename sheet, and single-chat actions for the drawer. */
export function useChatMenuActions({
  token, isDrawerOpen, patchChatInGroups, insertChatInGroups,
  moveChatPinState, moveChatArchiveState, removeChatFromGroupsById,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const { view, owns, mounted } = useViewOwner(`${session}:${isDrawerOpen}`);
  // The menu, rename sheet and share sheet each belong to the view they opened in.
  const [menu, setMenu] = useState<{ chat: Chat; view: object } | null>(null);
  const [rename, setRename] = useState<{ chat: Chat; view: object } | null>(null);
  const [renameText, setRenameText] = useState("");
  const [share, setShare] = useState<{ chat: Chat; view: object } | null>(null);
  const menuChat = menu?.view === view ? menu.chat : null;
  const renameTarget = rename?.view === view ? rename.chat : null;
  const shareChat = share?.view === view ? share.chat : null;
  const shareRef = useLatestRef(shareChat);
  const [actionBanner, setActionBanner] = useState<{ message: string; icon?: IconName } | null>(null);
  const current = useCallback(() => mounted() && session === getSessionGeneration(), [mounted, session]);
  const currentView = useCallback(() => current() && isDrawerOpen && owns(), [current, isDrawerOpen, owns]);
  useEffect(() => {
    setMenu(null);
    setRename(null);
    setActionBanner(null);
    setShare(null);
  }, [session, isDrawerOpen]);

  const showActionBanner = useCallback((message: string, icon?: IconName) => {
    if (current()) setActionBanner({ message, icon });
  }, [current]);
  const dismissActionBanner = useCallback(() => setActionBanner(null), []);
  const closeMenu = useCallback(() => setMenu(null), []);
  const showRowMenu = useCallback((chat: Chat) => {
    if (currentView()) setMenu({ chat, view });
  }, [currentView, view]);
  const closeRename = useCallback(() => setRename(null), []);

  const openShareChat = useCallback(() => {
    if (!menuChat || !currentView()) return;
    const chat = getCachedChat(menuChat.id) ?? menuChat;
    closeMenu();
    setShare({ chat, view });
  }, [menuChat, currentView, closeMenu, view]);
  const closeShare = useCallback(() => setShare(null), []);
  /** Private history reaches the share sheet only while the drawer and account are unchanged. */
  const loadShareMessages = useCallback(async () => {
    const chat = shareRef.current;
    if (!token || !chat || !currentView()) throw new Error("share_closed");
    const msgs = await api.listAllMessages(token, chat.id);
    if (!currentView() || shareRef.current !== chat) throw new Error("share_closed");
    return msgs;
  }, [token, currentView, shareRef]);

  const openRenameFromMenu = useCallback(() => {
    if (!menuChat || !currentView()) return;
    const chat = getCachedChat(menuChat.id) ?? menuChat;
    setRename({ chat, view });
    setRenameText(chat.title ?? "");
    closeMenu();
  }, [menuChat, currentView, closeMenu, view]);

  const confirmRename = useCallback(async () => {
    if (!token || !renameTarget || !currentView()) return;
    const title = sanitizeManualChatTitle(renameText);
    if (!title) return;
    const release = beginChatMutation(session, [renameTarget.id]);
    if (!release) return;
    const chat = getCachedChat(renameTarget.id) ?? renameTarget;
    patchChatInGroups(chat.id, { title });
    closeRename();
    try {
      const saved = await api.renameChat(token, chat.id, title);
      if (!current()) return;
      patchChatInGroups(chat.id, { title: saved.title });
      showActionBanner(t("chat.renamed_toast"), "pencil");
    } catch {
      if (!current()) return;
      patchChatInGroups(chat.id, { title: chat.title });
      reportRecoverableError(feedback, t("chat.rename_failed"));
    } finally { release(); }
  }, [renameText, renameTarget, token, currentView, current, session, patchChatInGroups, closeRename, showActionBanner, feedback, t]);

  const togglePinChat = useCallback(async () => {
    if (!token || !menuChat || !currentView()) return;
    const chat = getCachedChat(menuChat.id) ?? menuChat;
    if (chat.archived) return;
    const release = beginChatMutation(session, [chat.id]);
    if (!release) return;
    const next = !chat.pinned;
    closeMenu();
    moveChatPinState(chat.id, next);
    try {
      const saved = await api.setPin(token, chat.id, next);
      if (!current()) return;
      patchChatInGroups(chat.id, { pinned: saved.pinned, archived: saved.archived });
      showActionBanner(saved.pinned ? t("chat.pinned_toast") : t("chat.unpinned_toast"), saved.pinned ? "pin" : "pin-off");
    } catch {
      if (!current()) return;
      moveChatPinState(chat.id, chat.pinned);
      reportRecoverableError(feedback, t("chat.pin_failed"));
    } finally { release(); }
  }, [token, menuChat, currentView, current, session, closeMenu, moveChatPinState, patchChatInGroups, showActionBanner, feedback, t]);

  const toggleArchiveChat = useCallback(async () => {
    if (!token || !menuChat || !currentView()) return;
    const chat = getCachedChat(menuChat.id) ?? menuChat;
    const release = beginChatMutation(session, [chat.id]);
    if (!release) return;
    const next = !chat.archived;
    closeMenu();
    moveChatArchiveState(chat.id, next);
    try {
      const saved = await api.setArchive(token, chat.id, next);
      if (!current()) return;
      patchChatInGroups(chat.id, { archived: saved.archived, pinned: saved.pinned });
      showActionBanner(saved.archived ? t("chat.archived_toast") : t("chat.unarchived_toast"), saved.archived ? "archive" : "unarchive");
    } catch {
      if (!current()) return;
      patchChatInGroups(chat.id, { archived: chat.archived ?? false, pinned: chat.pinned });
      reportRecoverableError(feedback, t("common.error"));
    } finally { release(); }
  }, [token, menuChat, currentView, current, session, closeMenu, moveChatArchiveState, patchChatInGroups, showActionBanner, feedback, t]);

  const requestDeleteChat = useCallback((chat: Chat) => {
    void confirmDialog({
      title: t("chat.delete_confirm_title"),
      message: t("chat.delete_confirm_body"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("common.delete"),
      destructive: true,
    }).then(async (ok) => {
      if (!ok) return;
      if (!token || !currentView()) return;
      const release = beginChatMutation(session, [chat.id]);
      if (!release) return;
      const snapshot = getCachedChat(chat.id) ?? chat;
      removeChatFromGroupsById(chat.id);
      try {
        await api.deleteChat(token, chat.id);
        if (!current()) return;
        notifyDestructive();
        removeChatFromGroupsById(chat.id);
        void clearCachedChatMessages(chat.id);
        emitAppEvent("chatsDeleted", { chatIds: [chat.id] });
        abandonActiveChatIfDeleted([chat.id]);
        showActionBanner(t("chat.deleted_toast"), "trash");
      } catch {
        if (!current()) return;
        insertChatInGroups(snapshot);
        reportRecoverableError(feedback, t("chat.delete_failed"));
      } finally { release(); }
    });
  }, [token, currentView, current, session, removeChatFromGroupsById, insertChatInGroups, showActionBanner, feedback, t]);
  const confirmDeleteChat = useCallback(() => {
    if (!menuChat || !currentView()) return;
    const chat = menuChat;
    closeMenu();
    requestDeleteChat(chat);
  }, [menuChat, currentView, closeMenu, requestDeleteChat]);

  return {
    menuChat,
    renameVisible: renameTarget !== null,
    renameText, setRenameText, actionBanner, dismissActionBanner, showActionBanner,
    closeMenu, showRowMenu, openRenameFromMenu, confirmRename,
    shareChat, openShareChat, closeShare, loadShareMessages,
    togglePinChat, toggleArchiveChat, confirmDeleteChat, closeRename,
  };
}
