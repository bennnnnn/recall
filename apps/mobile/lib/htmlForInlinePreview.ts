/** Strip document shell and return markup react-native-render-html can display. */
export function htmlForInlinePreview(html: string): string {
  const trimmed = html.trim();
  if (!trimmed) return "<p><strong>(empty)</strong></p>";

  let inner = trimmed;

  if (/^\s*<!DOCTYPE/i.test(trimmed) || /^\s*<html/i.test(trimmed)) {
    const bodyMatch = trimmed.match(/<body[^>]*>([\s\S]*?)<\/body[^>]*>/i);
    if (bodyMatch?.[1]) {
      inner = bodyMatch[1].trim();
    } else {
      inner = trimmed
        .replace(/<!DOCTYPE[^>]*>/gi, "")
        .replace(/<\/?html[^>]*>/gi, "")
        .replace(/(?:<head\b[^>]*>[\s\S]*?<\/head[^>]*>)+/gi, "")
        .replace(/<\/?body[^>]*>/gi, "")
        .trim();
      // Loop head strip until stable (nested / overlapping shapes).
      let prev = "";
      for (let i = 0; i < 8 && inner !== prev; i++) {
        prev = inner;
        inner = inner.replace(/<head\b[^>]*>[\s\S]*?<\/head[^>]*>/gi, "").trim();
      }
    }
  }

  // Strip inert style/script blocks until stable — a single pass can leave
  // residual tags (CodeQL js/incomplete-multi-character-sanitization).
  let cleaned = inner;
  let prev = "";
  for (let i = 0; i < 16 && cleaned !== prev; i++) {
    prev = cleaned;
    cleaned = cleaned
      .replace(/<style\b[^>]*>[\s\S]*?<\/style[^>]*>/gi, "")
      .replace(/<script\b[^>]*>[\s\S]*?<\/script[^>]*>/gi, "")
      .replace(/<script\b[^>]*\/>/gi, "");
  }
  inner = cleaned;

  const visibleText = inner.replace(/<[^>]+>/g, "").trim();
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
  let textOnly = inner;
  let prev = "";
  for (let i = 0; i < 8 && textOnly !== prev; i++) {
    prev = textOnly;
    textOnly = textOnly.replace(/<[^>]+>/g, "");
  }
  return /\p{L}|\p{N}/u.test(textOnly);
}
