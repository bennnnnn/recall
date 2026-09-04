import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "react-native";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, Chat } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { clearCachedChatMessages } from "@/lib/chatMessageCache";
import { getCachedChat } from "@/lib/cache/chatListCache";
import { invalidateGalleryCache } from "@/lib/cache/galleryListCache";
import { abandonActiveChatIfDeleted } from "@/lib/drawer";
import { type IoniconName } from "@/lib/icons";
import { beginChatMutation } from "@/lib/chat/chatMutationLock";
import { sanitizeManualChatTitle } from "@/lib/chat/chatTitle";
import { isShareCancelled } from "@/lib/exportPdf";
import { shareConversation } from "@/lib/share";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

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
  const mounted = useRef(true);
  const view = useRef({ session, isDrawerOpen, version: 0 });
  if (view.current.session !== session || view.current.isDrawerOpen !== isDrawerOpen) {
    view.current = { session, isDrawerOpen, version: view.current.version + 1 };
  }
  const [menuChat, setMenuChat] = useState<Chat | null>(null);
  const menuRef = useRef(menuChat);
  menuRef.current = menuChat;
  const [renameVisible, setRenameVisible] = useState(false);
  const [renameText, setRenameText] = useState("");
  const [renameTarget, setRenameTarget] = useState<Chat | null>(null);
  const sharing = useRef(false);
  const [actionBanner, setActionBanner] = useState<{ message: string; icon?: IoniconName } | null>(null);
  const current = useCallback(() => mounted.current && session === getSessionGeneration(), [session]);
  const viewVersion = view.current.version;
  const currentView = useCallback(() => current() && view.current.isDrawerOpen && view.current.version === viewVersion, [current, viewVersion]);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    setMenuChat(null);
    setRenameVisible(false);
    setRenameTarget(null);
    setActionBanner(null);
  }, [session, isDrawerOpen]);

  const showActionBanner = useCallback((message: string, icon?: IoniconName) => {
    if (current()) setActionBanner({ message, icon });
  }, [current]);
  const dismissActionBanner = useCallback(() => setActionBanner(null), []);
  const closeMenu = useCallback(() => { menuRef.current = null; setMenuChat(null); }, []);
  const showRowMenu = useCallback((chat: Chat) => {
    if (currentView()) { menuRef.current = chat; setMenuChat(chat); }
  }, [currentView]);
  const closeRename = useCallback(() => { setRenameVisible(false); setRenameTarget(null); }, []);

  const handleShareChat = useCallback(async () => {
    if (!token || !menuChat || !currentView() || sharing.current) return;
    const chat = getCachedChat(menuChat.id) ?? menuChat;
    const selectedMenu = menuRef.current;
    const shareCurrent = () => currentView() && menuRef.current === selectedMenu;
    sharing.current = true;
    try {
      const msgs = await api.listAllMessages(token, chat.id);
      if (!shareCurrent()) return;
      // Keep the menu mounted while presenting the iOS activity controller.
      await shareConversation(chat.title, msgs);
    } catch (error) {
      if (shareCurrent() && !isShareCancelled(error)) reportRecoverableError(feedback, t("chat.share_failed"));
    } finally {
      sharing.current = false;
      if (shareCurrent()) closeMenu();
    }
  }, [token, menuChat, currentView, closeMenu, feedback, t]);

  const openRenameFromMenu = useCallback(() => {
    if (!menuChat || !currentView()) return;
    const chat = getCachedChat(menuChat.id) ?? menuChat;
    setRenameTarget(chat);
    setRenameText(chat.title ?? "");
    closeMenu();
    setRenameVisible(true);
  }, [menuChat, currentView, closeMenu]);

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
      showActionBanner(t("chat.renamed_toast"), "pencil-outline");
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
      showActionBanner(next ? t("chat.pinned_toast") : t("chat.unpinned_toast"), next ? "pin" : "pin-outline");
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
      showActionBanner(next ? t("chat.archived_toast") : t("chat.unarchived_toast"), next ? "archive-outline" : "arrow-undo-outline");
    } catch {
      if (!current()) return;
      patchChatInGroups(chat.id, { archived: chat.archived ?? false, pinned: chat.pinned });
      reportRecoverableError(feedback, t("common.error"));
    } finally { release(); }
  }, [token, menuChat, currentView, current, session, closeMenu, moveChatArchiveState, patchChatInGroups, showActionBanner, feedback, t]);

  const requestDeleteChat = useCallback((chat: Chat) => {
    Alert.alert(t("chat.delete_confirm_title"), t("chat.delete_confirm_body"), [
      { text: t("common.cancel"), style: "cancel" },
      { text: t("common.delete"), style: "destructive", onPress: async () => {
        if (!token || !currentView()) return;
        const release = beginChatMutation(session, [chat.id]);
        if (!release) return;
        const snapshot = getCachedChat(chat.id) ?? chat;
        removeChatFromGroupsById(chat.id);
        try {
          await api.deleteChat(token, chat.id);
          if (!current()) return;
          removeChatFromGroupsById(chat.id);
          void clearCachedChatMessages(chat.id);
          invalidateGalleryCache();
          abandonActiveChatIfDeleted([chat.id]);
          showActionBanner(t("chat.deleted_toast"), "trash-outline");
        } catch {
          if (!current()) return;
          insertChatInGroups(snapshot);
          reportRecoverableError(feedback, t("chat.delete_failed"));
        } finally { release(); }
      } },
    ]);
  }, [token, currentView, current, session, removeChatFromGroupsById, insertChatInGroups, showActionBanner, feedback, t]);
  const confirmDeleteChat = useCallback(() => {
    if (!menuChat || !currentView()) return;
    const chat = menuChat;
    closeMenu();
    requestDeleteChat(chat);
  }, [menuChat, currentView, closeMenu, requestDeleteChat]);

  return {
    menuChat: currentView() ? menuChat : null,
    renameVisible: currentView() && renameVisible,
    renameText, setRenameText, actionBanner, dismissActionBanner, showActionBanner,
    closeMenu, showRowMenu, handleShareChat, openRenameFromMenu, confirmRename,
    togglePinChat, toggleArchiveChat, confirmDeleteChat, closeRename,
  };
}
