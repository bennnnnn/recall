import type { Message } from "@/lib/api";
import { printHtmlToSharedPdf } from "@/lib/exportPdf";
import i18n from "@/lib/i18n";
import { markdownToStructuredPrintHtml } from "@/lib/printDocument";
import { loadVendorText } from "@/lib/vendorAssets";
import { conversationMarkdownBody } from "@/features/chat/model/transcript";

async function exportMessageAsPdf(title: string, markdown: string): Promise<void> {
  // The KaTeX CSS (and its fonts) is read only when a reply is printed.
  const html = markdownToStructuredPrintHtml(title, markdown, await loadVendorText("katexCss"));
  await printHtmlToSharedPdf(html, title);
}

/** Print the full thread (user + assistant turns) as a PDF. */
export async function exportConversationAsPdf(
  title: string | null,
  messages: Message[],
): Promise<void> {
  const heading = title?.trim() || i18n.t("chat.export_pdf_default_title");
  const body = conversationMarkdownBody(messages);
  if (!body.trim()) return;
  await exportMessageAsPdf(heading, body);
}
