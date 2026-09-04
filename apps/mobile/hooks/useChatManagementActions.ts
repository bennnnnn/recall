import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "react-native";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { getCachedChat, peekCreatedChat } from "@/lib/cache/chatListCache";
import { invalidateGalleryCache } from "@/lib/cache/galleryListCache";
import { beginChatMutation } from "@/lib/chat/chatMutationLock";
import { sanitizeManualChatTitle } from "@/lib/chat/chatTitle";
import { clearCachedChatMessages } from "@/lib/chatMessageCache";
import { abandonActiveChatIfDeleted, insertChatGlobal, moveChatArchiveGlobal, patchChatGlobal, removeChatGlobal } from "@/lib/drawer";
import { tap } from "@/lib/haptics";
import type { IoniconName } from "@/lib/icons";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

type Options = {
  token: string | null;
  chatId: string | null;
  chatTitle: string | null;
  pinned: boolean;
  archived: boolean;
  setPinned: React.Dispatch<React.SetStateAction<boolean>>;
  setArchived: React.Dispatch<React.SetStateAction<boolean>>;
  setChatTitle: React.Dispatch<React.SetStateAction<string | null>>;
  closeMenu: () => void;
  dismissActionBanner: () => void;
  showActionBanner: (message: string, icon?: IoniconName) => void;
  t: (key: string, options?: Record<string, unknown>) => string;
};

/** Conversation management keeps server reconciliation separate from the current screen. */
export function useChatManagementActions({
  token, chatId, chatTitle, pinned, archived, setPinned, setArchived,
  setChatTitle, closeMenu, dismissActionBanner, showActionBanner, t,
}: Options) {
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const signedIn = Boolean(token);
  const viewRef = useRef({ chatId, session, signedIn });
  if (viewRef.current.chatId !== chatId || viewRef.current.session !== session || viewRef.current.signedIn !== signedIn) {
    viewRef.current = { chatId, session, signedIn };
  }
  const view = viewRef.current;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const currentSession = useCallback(() => session === getSessionGeneration(), [session]);
  const currentView = useCallback(
    () => mounted.current && viewRef.current === view && currentSession(), [view, currentSession],
  );
  const [renameVisible, setRenameVisible] = useState(false);
  const [renameText, setRenameText] = useState("");
  useEffect(() => {
    setRenameVisible(false);
    setRenameText("");
    closeMenu();
    dismissActionBanner();
  }, [view, closeMenu, dismissActionBanner]);

  const openRename = useCallback(() => {
    if (!currentView()) return;
    setRenameText(chatTitle ?? "");
    setRenameVisible(true);
  }, [chatTitle, currentView]);

  const confirmRename = useCallback(async () => {
    if (!currentView()) return;
    const title = sanitizeManualChatTitle(renameText);
    if (!title || !chatId || !token) {
      setRenameVisible(false);
      return;
    }
    const release = beginChatMutation(session, [chatId]);
    if (!release) return;
    const previousTitle = chatTitle;
    setChatTitle(title);
    patchChatGlobal(chatId, { title });
    setRenameVisible(false);
    try {
      const updated = await api.renameChat(token, chatId, title);
      if (!currentSession()) return;
      patchChatGlobal(chatId, { title: updated.title });
      if (currentView()) {
        setChatTitle(updated.title);
        showActionBanner(t("chat.renamed_toast"), "pencil-outline");
      }
    } catch {
      if (!currentSession()) return;
      patchChatGlobal(chatId, { title: previousTitle });
      if (currentView()) {
        setChatTitle(previousTitle);
        reportRecoverableError(feedback, t("chat.rename_failed"));
      }
    } finally { release(); }
  }, [currentView, renameText, chatId, token, session, chatTitle, setChatTitle, currentSession, showActionBanner, t, feedback]);

  const togglePin = useCallback(async () => {
    if (!chatId || !token || archived || !currentView()) return;
    const release = beginChatMutation(session, [chatId]);
    if (!release) return;
    tap();
    const next = !pinned;
    setPinned(next);
    patchChatGlobal(chatId, { pinned: next });
    try {
      await api.setPin(token, chatId, next);
      if (!currentSession()) return;
      patchChatGlobal(chatId, { pinned: next });
      if (currentView()) {
        setPinned(next);
        showActionBanner(next ? t("chat.pinned_toast") : t("chat.unpinned_toast"), next ? "pin" : "pin-outline");
      }
    } catch {
      if (!currentSession()) return;
      patchChatGlobal(chatId, { pinned });
      if (currentView()) {
        setPinned(pinned);
        reportRecoverableError(feedback, t("chat.pin_failed"));
      }
    } finally { release(); }
  }, [chatId, token, archived, currentView, session, pinned, setPinned, showActionBanner, t, currentSession, feedback]);

  const toggleArchive = useCallback(async () => {
    if (!chatId || !token || !currentView()) return;
    const release = beginChatMutation(session, [chatId]);
    if (!release) return;
    tap();
    const next = !archived;
    setArchived(next);
    if (next) setPinned(false);
    moveChatArchiveGlobal(chatId, next);
    try {
      await api.setArchive(token, chatId, next);
      if (!currentSession()) return;
      moveChatArchiveGlobal(chatId, next);
      if (currentView()) {
        setArchived(next);
        if (next) setPinned(false);
        showActionBanner(next ? t("chat.archived_toast") : t("chat.unarchived_toast"), next ? "archive-outline" : "arrow-undo-outline");
      }
    } catch {
      if (!currentSession()) return;
      moveChatArchiveGlobal(chatId, archived);
      patchChatGlobal(chatId, { pinned });
      if (currentView()) {
        setArchived(archived);
        setPinned(pinned);
        reportRecoverableError(feedback, t("chat.archive_failed"));
      }
    } finally { release(); }
  }, [chatId, token, currentView, session, archived, setArchived, setPinned, pinned, showActionBanner, t, currentSession, feedback]);

  const confirmDelete = useCallback(() => {
    if (!chatId || !token || !currentView()) return;
    Alert.alert(t("chat.delete_confirm_title"), t("chat.delete_confirm_body"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"), style: "destructive",
        onPress: async () => {
          if (!currentView()) return;
          const release = beginChatMutation(session, [chatId]);
          if (!release) return;
          const snapshot = getCachedChat(chatId) ?? peekCreatedChat(chatId);
          removeChatGlobal(chatId);
          try {
            await api.deleteChat(token, chatId);
            if (!currentSession()) return;
            removeChatGlobal(chatId);
            void clearCachedChatMessages(chatId);
            invalidateGalleryCache();
            if (currentView()) showActionBanner(t("chat.deleted_toast"), "trash-outline");
            abandonActiveChatIfDeleted([chatId]);
          } catch {
            if (!currentSession()) return;
            // A failed delete must preserve original dates and project/quiz
            // metadata. A chat absent from the list needs its real server row.
            const restored = snapshot ?? await api.getChat(token, chatId).catch(() => null);
            if (!currentSession()) return;
            if (restored) insertChatGlobal(restored);
            if (currentView()) reportRecoverableError(feedback, t("chat.delete_failed"));
          } finally { release(); }
        },
      },
    ]);
  }, [chatId, token, currentView, t, session, currentSession, showActionBanner, feedback]);

  return { renameVisible, setRenameVisible, renameText, setRenameText, openRename, confirmRename, togglePin, toggleArchive, confirmDelete };
}
