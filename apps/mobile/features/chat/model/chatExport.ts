/**
 * A chat leaves Recall two ways, from either chat menu (the chat's ⋮ and the drawer row):
 * as text through the OS share menu, its contacts and every app, so a chat spreads (the
 * user, 2026-11-07, over Recall's own sheet of Share / Copy / PDF first), or as a PDF.
 * A closed share or print sheet is not a failure.
 */
import i18n from "@/lib/i18n";
import type { Message } from "@/lib/api";
import { presentShareSheet } from "@/lib/share";
import { isShareCancelled } from "@/lib/shareCancelled";
import { shareOneAtATime } from "@/lib/shareFile";
import { shareFailureKey } from "@/lib/shareUnavailable";
import { NothingToExportError } from "@/features/chat/model/nothingToExport";
import { conversationTranscript } from "@/features/chat/model/transcript";

/** The i18n key of what went wrong, for the caller's own feedback. */
type Fail = (key: string) => void;

/** Every message of the chat, read when the export starts; it throws when the chat is gone. */
type Load = () => Promise<Message[]>;

export async function shareChatAsText(title: string | null, load: Load, fail: Fail): Promise<void> {
  try {
    const message = conversationTranscript(title, await load());
    await presentShareSheet({ message, title: title?.trim() || i18n.t("share.default_title") });
  } catch (error) {
    if (!isShareCancelled(error)) fail(shareFailureKey(error, "chat.share_failed"));
  }
}

/**
 * `preparing` shows until the PDF's share sheet opens (`ready`): the first export takes seconds.
 * A second export asked for meanwhile (the menu opens again) is dropped, not refused as a failure.
 */
export async function exportChatAsPdf(
  title: string | null,
  load: Load,
  report: { preparing: () => void; ready: () => void; fail: Fail },
): Promise<void> {
  await shareOneAtATime(async () => {
    report.preparing();
    try {
      // MathJax and expo-print load when a PDF is asked for, not with the chat.
      const [messages, { exportConversationAsPdf }] = await Promise.all([
        load(),
        import("@/features/chat/model/exportMessagePdf"),
      ]);
      await exportConversationAsPdf(title, messages, report.ready);
    } catch (error) {
      report.ready();
      if (isShareCancelled(error)) return;
      report.fail(
        error instanceof NothingToExportError ? "chat.export_pdf_empty" : shareFailureKey(error, "chat.export_pdf_failed"),
      );
    }
  });
}
