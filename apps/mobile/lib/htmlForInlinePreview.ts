/** Strip document shell and return markup react-native-render-html can display. */
export function htmlForInlinePreview(html: string): string {
  const trimmed = html.trim();
  if (!trimmed) return "<p><strong>(empty)</strong></p>";

  let inner = trimmed;

  if (/^\s*<!DOCTYPE/i.test(trimmed) || /^\s*<html/i.test(trimmed)) {
    const bodyMatch = trimmed.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    if (bodyMatch?.[1]) {
      inner = bodyMatch[1].trim();
    } else {
      inner = trimmed
        .replace(/<!DOCTYPE[^>]*>/gi, "")
        .replace(/<\/?html[^>]*>/gi, "")
        .replace(/<head[\s\S]*?<\/head>/gi, "")
        .replace(/<\/?body[^>]*>/gi, "")
        .trim();
    }
  }

  const visibleText = inner.replace(/<style[\s\S]*?<\/style>/gi, "").replace(/<[^>]+>/g, "").trim();
  if (!visibleText && !/<img\b/i.test(inner)) {
    const escaped = trimmed
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return `<p>This page relies on CSS or JavaScript. Use <strong>Open in Safari</strong> for the live version.</p><pre>${escaped.slice(0, 4000)}</pre>`;
  }

  return `<div>${inner}</div>`;
}

export function previewHasVisibleText(html: string): boolean {
  const inner = htmlForInlinePreview(html);
  return /\p{L}|\p{N}/u.test(inner.replace(/<[^>]+>/g, ""));
}
