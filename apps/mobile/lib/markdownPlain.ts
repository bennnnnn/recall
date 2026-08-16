/** Strip common markdown to plain text for TTS (and other non-print uses).
 * Do not import printDocument here — that module statically loads KaTeX. */

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
