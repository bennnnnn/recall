import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import type { Chat } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { useViewOwner } from "@/features/chat/hooks/useViewOwner";
import { getCachedChat } from "@/features/chat/model/chatListCache";
import { useChatExportActions } from "@/features/chat/hooks/useChatExportActions";
import {
  confirmAndDeleteChat,
  renameChat,
  setChatArchived,
  setChatPinned,
  type ChatOperationContext,
} from "@/features/chat/model/chatOperations";
import type { IconName } from "@/ui/icons/names";
import { useLatestRef } from "@/lib/latestRef";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

/** What a drawer row's long-press menu does to its chat, also offered to screen readers on the row. */
export type ChatRowAction = "share" | "rename" | "pin" | "archive" | "delete";

type Params = {
  token: string | null;
  isDrawerOpen: boolean;
  patchChatInGroups: (chatId: string, patch: Partial<Chat>) => void;
  insertChatInGroups: (chat: Chat) => void;
  removeChatFromGroupsById: (chatId: string) => void;
};

/** Row-menu, rename sheet, and single-chat actions for the drawer. */
export function useChatMenuActions({
  token, isDrawerOpen, patchChatInGroups, insertChatInGroups, removeChatFromGroupsById,
}: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();
  const session = getSessionGeneration();
  const { view, owns, mounted } = useViewOwner(`${session}:${isDrawerOpen}`);
  // The menu and rename sheet each belong to the view they opened in.
  const [menu, setMenu] = useState<{ chat: Chat; view: object } | null>(null);
  const [rename, setRename] = useState<{ chat: Chat; view: object } | null>(null);
  const [renameText, setRenameText] = useState("");
  const menuChat = menu?.view === view ? menu.chat : null;
  const renameTarget = rename?.view === view ? rename.chat : null;
  const [actionBanner, setActionBanner] = useState<{ message: string; icon?: IconName } | null>(null);
  const current = useCallback(() => mounted() && session === getSessionGeneration(), [mounted, session]);
  const currentView = useCallback(() => current() && isDrawerOpen && owns(), [current, isDrawerOpen, owns]);
  useEffect(() => {
    setMenu(null);
    setRename(null);
    setActionBanner(null);
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

  const { shareChat, exportChatPdf } = useChatExportActions({
    token, chat: menuChat, currentView, closeMenu, showActionBanner, dismissActionBanner,
  });

  const operations = useMemo<ChatOperationContext | null>(
    () =>
      token
        ? {
            token,
            session,
            list: { patch: patchChatInGroups, insert: insertChatInGroups, remove: removeChatFromGroupsById },
            signedIn: current,
            shown: currentView,
            banner: showActionBanner,
            failure: (message: string) => reportRecoverableError(feedback, message),
            t,
          }
        : null,
    [token, session, patchChatInGroups, insertChatInGroups, removeChatFromGroupsById, current, currentView, showActionBanner, feedback, t],
  );

  const confirmRename = useCallback(async () => {
    if (!operations || !renameTarget || !currentView()) return;
    const chat = getCachedChat(renameTarget.id) ?? renameTarget;
    if (renameChat(operations, chat, renameText)) closeRename();
  }, [operations, renameTarget, currentView, renameText, closeRename]);

  // One of a chat's actions on the chat itself: from its row menu, or a screen reader's action
  // on the row (no menu open).
  const runChatAction = useCallback(async (target: Chat, action: ChatRowAction) => {
    if (!currentView()) return;
    const chat = getCachedChat(target.id) ?? target;
    if (action === "share") return shareChat(chat);
    if (action === "rename") {
      setRename({ chat, view });
      setRenameText(chat.title ?? "");
      return closeMenu();
    }
    if (!operations || (action === "pin" && chat.archived)) return;
    closeMenu();
    if (action === "pin") await setChatPinned(operations, chat, !chat.pinned);
    else if (action === "archive") await setChatArchived(operations, chat, !chat.archived);
    else confirmAndDeleteChat(operations, chat.id, chat);
  }, [currentView, shareChat, view, closeMenu, operations]);
  const onMenuChat = (action: ChatRowAction) => async () => {
    if (menuChat) await runChatAction(menuChat, action);
  };
  // Every row holds this one: a handler renewed with each menu would redraw them all.
  const latestAction = useLatestRef(runChatAction);
  const rowAction = useCallback((chat: Chat, action: ChatRowAction) => void latestAction.current(chat, action), [latestAction]);

  return {
    menuChat,
    renameVisible: renameTarget !== null,
    renameText, setRenameText, actionBanner, dismissActionBanner, showActionBanner,
    closeMenu, showRowMenu, openRenameFromMenu: onMenuChat("rename"), confirmRename,
    openShareChat: onMenuChat("share"), exportChatPdf, rowAction,
    togglePinChat: onMenuChat("pin"), toggleArchiveChat: onMenuChat("archive"), confirmDeleteChat: onMenuChat("delete"), closeRename,
  };
}
