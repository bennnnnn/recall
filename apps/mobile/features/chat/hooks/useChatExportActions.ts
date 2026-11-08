import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api, type Chat } from "@/lib/api";
import { getCachedChat } from "@/features/chat/model/chatListCache";
import { exportChatAsPdf, shareChatAsText } from "@/features/chat/model/chatExport";
import type { IconName } from "@/ui/icons/names";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

type Params = {
  token: string | null;
  /** The chat whose row menu is open. */
  chat: Chat | null;
  /** The drawer and account the menu opened in are still the ones on screen. */
  currentView: () => boolean;
  closeMenu: () => void;
  showActionBanner: (message: string, icon?: IconName) => void;
  dismissActionBanner: () => void;
};

/**
 * A drawer row menu's Share (the OS share menu, with the chat as text) and Export PDF. The
 * chat's private history is read only while the drawer and account are unchanged, and a
 * failure after either changed stays quiet.
 */
export function useChatExportActions({ token, chat: menuChat, currentView, closeMenu, showActionBanner, dismissActionBanner }: Params) {
  const { t } = useTranslation();
  const feedback = useActionFeedbackOptional();

  const target = useCallback((chosen: Chat | null) => {
    if (!token || !chosen || !currentView()) return null;
    const chat = getCachedChat(chosen.id) ?? chosen;
    closeMenu();
    const load = async () => {
      const msgs = await api.listAllMessages(token, chat.id);
      if (!currentView()) throw new Error("share_closed");
      return msgs;
    };
    const fail = (key: string) => {
      if (currentView()) reportRecoverableError(feedback, t(key));
    };
    return { title: chat.title ?? null, load, fail };
  }, [token, currentView, closeMenu, feedback, t]);

  /** Shares `chat`: the menu's, or a row's when a screen reader picks Share on it. */
  const shareChat = useCallback((chosen: Chat) => {
    const chat = target(chosen);
    if (chat) void shareChatAsText(chat.title, chat.load, chat.fail);
  }, [target]);

  const exportChatPdf = useCallback(() => {
    const chat = target(menuChat);
    if (!chat) return;
    void exportChatAsPdf(chat.title, chat.load, {
      preparing: () => showActionBanner(t("chat.status.preparing"), "file-text"),
      ready: dismissActionBanner,
      fail: chat.fail,
    });
  }, [target, menuChat, showActionBanner, dismissActionBanner, t]);

  return { shareChat, exportChatPdf };
}
