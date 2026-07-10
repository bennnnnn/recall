import { printHtmlToSharedPdf } from "@/lib/exportPdf";
import { markdownToStructuredPrintHtml } from "@/lib/printDocument";

export async function exportMessageAsPdf(title: string, markdown: string): Promise<void> {
  const html = markdownToStructuredPrintHtml(title, markdown);
  await printHtmlToSharedPdf(html, title);
}
