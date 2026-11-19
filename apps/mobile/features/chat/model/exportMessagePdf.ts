import type { Message } from "@/lib/api";
import { printHtmlToSharedPdf } from "@/features/chat/model/exportPdf";
import i18n from "@/lib/i18n";
import { markdownToStructuredPrintHtml } from "@/features/chat/model/printDocument";
import { NothingToExportError } from "@/features/chat/model/nothingToExport";
import { conversationMarkdownBody } from "@/features/chat/model/transcript";
import { shareFooterLines } from "@/features/chat/model/shareFooter";

async function exportMessageAsPdf(title: string, markdown: string, onSharing: () => void): Promise<void> {
  const html = await markdownToStructuredPrintHtml(title, markdown);
  await printHtmlToSharedPdf(html, title, () => true, onSharing);
}

/** Print the full thread (user + assistant turns) as a PDF; `onSharing` runs as the share sheet opens. */
export async function exportConversationAsPdf(
  title: string | null,
  messages: Message[],
  onSharing: () => void = () => {},
): Promise<void> {
  const heading = title?.trim() || i18n.t("chat.export_pdf_default_title");
  const body = conversationMarkdownBody(messages, "print");
  if (!body.trim()) throw new NothingToExportError();
  // The PDF ends as a text share does: where it came from, and where to get the app.
  const footer = shareFooterLines(undefined, (link) => `[${link}](${link})`)
    .map((line) => `*${line}*`)
    .join("\n\n");
  await exportMessageAsPdf(heading, `${body}\n\n---\n\n${footer}`, onSharing);
}
