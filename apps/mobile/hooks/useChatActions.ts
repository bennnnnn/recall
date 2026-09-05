import { useCallback, useRef, useState } from "react";
import { useRouter } from "expo-router";

import { type IoniconName } from "@/lib/icons";

import { api, type Message } from "@/lib/api";
import { patchCachedChatMessage } from "@/lib/chatMessageCache";
import { exportConversationAsPdf } from "@/lib/exportMessagePdf";
import { isShareCancelled } from "@/lib/exportPdf";
import { tap } from "@/lib/haptics";
import { shareConversation } from "@/lib/share";
import { useChatManagementActions } from "@/hooks/useChatManagementActions";
import { fullEmailText } from "@/lib/emailCompose";
import { replaceFirstClosedFenceBody } from "@/lib/mdFenceScan";
import type { EmailDraft } from "@/lib/richBlocks";
import { isServerMessageId } from "@/lib/serverMessageId";
import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { reportRecoverableError } from "@/lib/reportRecoverableError";

type Router = ReturnType<typeof useRouter>;

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
  hasMoreOlder?: boolean;
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
  t,
}: Options) {
  const feedback = useActionFeedbackOptional();
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const emailSavesRef = useRef(new Map<string, Promise<boolean>>());
  const [menuVisible, setMenuVisible] = useState(false);
  const [actionBanner, setActionBanner] = useState<{
    message: string;
    icon?: IoniconName;
  } | null>(null);

  const showActionBanner = useCallback(
    (message: string, icon?: IoniconName) => {
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
      if (token && chatId && isServerMessageId(messageId)) {
        void api.setMessageFeedback(token, chatId, messageId, next).catch(() => {
          setMessages((prev) =>
            prev.map((mm) =>
              mm.id === messageId ? { ...mm, feedback: previous } : mm,
            ),
          );
          reportRecoverableError(feedback, t("chat.feedback_failed"));
        });
      }
    },
    [token, chatId, setMessages, feedback, t],
  );

  const handleSaveEmailDraft = useCallback(
    (messageId: string, draft: EmailDraft): Promise<boolean> => {
      if (!token || !chatId || !isServerMessageId(messageId)) return Promise.resolve(false);
      const fenceBody = fullEmailText(draft);
      const message = messagesRef.current.find((m) => m.id === messageId);
      if (!message || message.role !== "assistant" ||
          replaceFirstClosedFenceBody(message.content, "email", fenceBody) == null) {
        return Promise.resolve(false);
      }
      // The card owns its unsaved fields. Never infer success from a React
      // state updater (which can run later or twice), or cache an unsaved edit.
      // Serialize writes so a slow earlier request cannot win on the server.
      const key = `${chatId}:${messageId}`;
      const pending = emailSavesRef.current.get(key) ?? Promise.resolve(true);
      const saving = pending.then(async () => {
        try {
        const updated = await api.updateMessageEmail(token, chatId, messageId, {
          to: draft.to,
          subject: draft.subject,
          body: draft.body,
        });
        setMessages((prev) =>
          prev.map((mm) =>
            mm.id === messageId ? { ...mm, content: updated.content } : mm,
          ),
        );
        void patchCachedChatMessage(chatId, messageId, { content: updated.content });
        return true;
      } catch {
        reportRecoverableError(feedback, t("chat.email_card_save_failed"));
        return false;
      }
      });
      emailSavesRef.current.set(key, saving);
      void saving.then(() => {
        if (emailSavesRef.current.get(key) === saving) emailSavesRef.current.delete(key);
      });
      return saving;
    },
    [token, chatId, setMessages, feedback, t],
  );

  const loadTranscriptMessages = useCallback(async () => {
    if (!token || !chatId) return messages;
    try {
      return await api.listAllMessages(token, chatId);
    } catch {
      return messages;
    }
  }, [token, chatId, messages]);

  const handleShare = useCallback(async () => {
    // Keep the ⋮ AppSheet up until Share.share returns. Closing the Modal
    // first tears down the presenter and iOS dismisses the activity sheet
    // with it — tap looks like a no-op.
    try {
      const transcript = await loadTranscriptMessages();
      await shareConversation(chatTitle, transcript);
    } catch (error) {
      if (isShareCancelled(error)) return;
      reportRecoverableError(feedback, t("chat.share_failed"));
    } finally {
      closeMenu();
    }
  }, [chatTitle, closeMenu, feedback, loadTranscriptMessages, t]);

  const handleExportPdf = useCallback(async () => {
    showActionBanner(t("chat.status.preparing"), "document-text-outline");
    try {
      const transcript = await loadTranscriptMessages();
      dismissActionBanner();
      await exportConversationAsPdf(chatTitle, transcript);
    } catch (error) {
      dismissActionBanner();
      if (isShareCancelled(error)) return;
      reportRecoverableError(feedback, t("chat.export_pdf_failed"));
    }
  }, [chatTitle, dismissActionBanner, loadTranscriptMessages, showActionBanner, feedback, t]);

  const {
    renameVisible, setRenameVisible, renameText, setRenameText,
    openRename, confirmRename, togglePin, toggleArchive, confirmDelete,
  } = useChatManagementActions({
    token, chatId, chatTitle, pinned, archived, setPinned, setArchived,
    setChatTitle, closeMenu, dismissActionBanner, showActionBanner, t,
  });

  const onShareFromMenu = useCallback(() => {
    tap();
    void handleShare();
  }, [handleShare]);

  const onExportPdfFromMenu = useCallback(() => {
    tap();
    closeMenu();
    void handleExportPdf();
  }, [closeMenu, handleExportPdf]);

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
    handleSaveEmailDraft,
    handleShare,
    handleExportPdf,
    openRename,
    confirmRename,
    togglePin,
    toggleArchive,
    confirmDelete,
    onShareFromMenu,
    onExportPdfFromMenu,
    onRenameFromMenu,
    onTogglePinFromMenu,
    onToggleArchiveFromMenu,
    onDeleteFromMenu,
  };
}
