import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import type { Message } from "@/lib/api";
import { conversationTranscript } from "@/lib/chat/transcript";
import { formatMonthDayYear } from "@/lib/datetime/format";
import { ShareSheet } from "@/ui/share/ShareSheet";

const APP_ICON = require("@/assets/images/icon.png");

type Props = {
  visible: boolean;
  onClose: () => void;
  title: string | null;
  /** Every message in the chat. Loaded once each time the sheet opens. */
  loadMessages: () => Promise<Message[]>;
};

/** Share a chat as it is now: the OS share menu, Copy, or a PDF. */
export function ChatShareSheet({ visible, onClose, title, loadMessages }: Props) {
  const { t } = useTranslation();
  const messages = useRef<Promise<Message[]> | null>(null);
  const loadRef = useRef(loadMessages);
  loadRef.current = loadMessages;

  useEffect(() => {
    if (!visible) messages.current = null;
  }, [visible]);

  const getMessages = () => {
    if (!messages.current) {
      const pending = loadRef.current();
      messages.current = pending;
      pending.catch(() => {
        if (messages.current === pending) messages.current = null;
      });
    }
    return messages.current;
  };

  const shownTitle = title?.trim() || t("share.default_title");

  return (
    <ShareSheet
      visible={visible}
      onClose={onClose}
      heading={t("share.chat_heading")}
      note={t("share.chat_note")}
      preview={{
        title: shownTitle,
        meta: `${t("app.name")} · ${formatMonthDayYear(new Date())}`,
        image: APP_ICON,
      }}
      load={async () => conversationTranscript(title, await getMessages())}
      shareTitle={shownTitle}
      onExportPdf={async () => {
        // expo-print loads only when a PDF is asked for.
        const { exportConversationAsPdf } = await import("@/lib/exportMessagePdf");
        await exportConversationAsPdf(title, await getMessages());
      }}
      labels={{
        share: t("share.action_share"),
        copy: t("share.action_copy"),
        copied: t("share.copied"),
        pdf: t("share.action_pdf"),
        copyText: t("share.copy_text"),
        failed: {
          share: t("chat.share_failed"),
          copy: t("share.copy_failed"),
          pdf: t("share.pdf_failed"),
        },
      }}
      testID="chat-share-sheet"
    />
  );
}
