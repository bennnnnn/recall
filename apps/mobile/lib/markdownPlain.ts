/** Strip common markdown to plain text for TTS and PDF export. */
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

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function markdownToPrintHtml(title: string, markdown: string): string {
  const plain = markdownToPlainText(markdown);
  const body = escapeHtml(plain).replace(/\n/g, "<br/>");
  const safeTitle = escapeHtml(title.trim() || "Recall report");
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 24px; color: #111; line-height: 1.5; }
  h1 { font-size: 22px; margin: 0 0 16px; }
  .body { font-size: 14px; white-space: normal; }
</style>
</head>
<body>
  <h1>${safeTitle}</h1>
  <div class="body">${body}</div>
</body>
</html>`;
}
