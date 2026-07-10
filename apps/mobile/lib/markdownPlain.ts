/** Strip common markdown to plain text for TTS (and other non-print uses). */

import { markdownToStructuredPrintHtml } from "@/lib/printDocument";

export function markdownToPlainText(markdown: string): string {
  let text = markdown;
  text = text.replace(/```[\s\S]*?```/g, " ");
  text = text.replace(/!\[[^\]]*\]\([^)]+\)/g, " ");
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  text = text.replace(/^#{1,6}\s+/gm, "");
  text = text.replace(/^\s*[-*+]\s+/gm, "• ");
  text = text.replace(/^\s*\d+\.\s+/gm, "");
  text = text.replace(/(\*\*|__|\*|_|`|~~)/g, "");
  text = text.replace(/\n{3,}/g, "\n\n");
  return text.trim();
}

/** Structured print HTML for message PDF export. */
export function markdownToPrintHtml(title: string, markdown: string): string {
  return markdownToStructuredPrintHtml(title, markdown);
}
