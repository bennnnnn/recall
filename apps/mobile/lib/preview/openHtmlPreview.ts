import {
  cacheDirectory,
  writeAsStringAsync,
  EncodingType,
} from "expo-file-system/legacy";
import * as WebBrowser from "expo-web-browser";
import { Linking } from "react-native";
import { newAccountFile } from "@/lib/accountFiles";
import { shareLocalFile } from "@/lib/shareFile";
import { stripScripts } from "@/lib/preview/htmlScriptStrip";
import { HTML_EXPORT_CSP, cspMetaTag, injectAtHeadStart } from "@/lib/preview/previewSandbox";
import type { Theme } from "@/lib/theme";
import { CODE_FONT } from "@/lib/fonts";

/**
 * Wrap bare HTML into a full document.
 *
 * `theme` threads app palette tokens into the document so the in-app Run tab
 * matches the active color scheme (dark mode no longer renders a white sheet).
 * Omit `theme` for the system-browser export path, which keeps light-only
 * defaults and lets the browser chrome control its own scheme. A document that
 * already has its own `<!DOCTYPE>`/`<html>` shell is returned unchanged — its
 * embedded styles are the author's choice, not ours to rewrite.
 */
export function wrapFullDocument(html: string, theme?: Theme): string {
  if (/^\s*<!DOCTYPE/i.test(html) || /^\s*<html/i.test(html)) {
    return html;
  }
  const bg = theme?.bg ?? "#FFFFFF";
  const text = theme?.text ?? "#111827";
  const border = theme?.border ?? "#E5E7EB";
  const thBg = theme?.surface ?? "#F1F5F9";
  const preBg = theme?.codeBg ?? "#F1F5F9";
  const codeFont = `'${CODE_FONT}', monospace`;
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 16px; line-height: 1.5; color: ${text}; background: ${bg}; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0; }
  td, th { border: 1px solid ${border}; padding: 8px; }
  th { background: ${thBg}; font-weight: 600; }
  pre { background: ${preBg}; padding: 12px; border-radius: 8px; overflow-x: auto; }
  code { font-family: ${codeFont}; font-size: 14px; font-variant-ligatures: none; }
  img { max-width: 100%; }
</style>
</head>
<body>
${html}
</body>
</html>`;
}

export function looksLikeInteractiveHtml(html: string): boolean {
  return /<\s*script\b/i.test(html);
}

/**
 * Starts the file. A file has no transport charset, so without it a browser
 * would decode the page by its own `<meta charset>`: ISO-2022-JP drops "ESC ( B"
 * and joins `http-equ` and `iv` into a pragma that disarming, which reads the
 * JS string, never saw. A byte-order mark settles the encoding before any meta.
 */
const UTF8_BOM = "\uFEFF";

/** First in the export, ahead of its CSP and the page: a second guard on the charset. */
const EXPORT_CHARSET_META = '<meta charset="utf-8">';

/** Android's share targets read the page's type; iOS reads it from the `.html` name. */
const HTML_MIME_TYPE = "text/html";

/** The page as a file in the cache directory, which sign-out clears. */
async function writeHtmlPreviewFile(html: string): Promise<string> {
  if (!cacheDirectory) throw new Error("html_preview_no_cache");
  const fileUri = newAccountFile("htmlPreview", "html");
  await writeAsStringAsync(fileUri, UTF8_BOM + html, { encoding: EncodingType.UTF8 });
  return fileUri;
}

/**
 * The document "Open in browser" and Share hand over: a static view of the
 * reply's HTML. The system browser (or whatever app opens the shared file) runs
 * `<script>` with no sandbox of ours, so model-generated JS is stripped, and the
 * document starts with a utf-8 charset and {@link HTML_EXPORT_CSP}, which
 * refuses every script even where the strip misses one. Interactive previews
 * run in the in-app WebView (CSP-sandboxed) instead.
 */
function htmlExportDocument(html: string): string {
  return injectAtHeadStart(
    wrapFullDocument(stripScripts(html)),
    EXPORT_CHARSET_META + cspMetaTag(HTML_EXPORT_CSP),
  );
}

/** Short enough to open as a `data:` URL; a longer page is opened from a file. */
const DATA_URL_MAX_CHARS = 120_000;

/** The ways a page is shown, in turn: the system's handler for the URL, then an in-app browser. */
const BROWSER_OPENERS = [(url: string) => Linking.openURL(url), (url: string) => WebBrowser.openBrowserAsync(url)];

/** True once a browser shows `url`. */
async function showInBrowser(url: string): Promise<boolean> {
  for (const open of BROWSER_OPENERS) {
    try {
      await open(url);
      return true;
    } catch (error) {
      // Expected on iOS, which opens neither data: nor file: URLs: the next way is tried.
      if (typeof __DEV__ !== "undefined" && __DEV__) console.info("[preview] a browser refused the page", error);
    }
  }
  return false;
}

/**
 * Open rendered HTML in the system browser (works in Expo Go); static view only. Where no
 * browser takes the page (iOS opens neither data: nor file: URLs) it goes to the share
 * sheet, as a file, whose apps can open it; `title` names that sheet. Throws when nothing
 * could show the page.
 */
export async function openHtmlInBrowser(html: string, title: string): Promise<void> {
  const fullHtml = htmlExportDocument(html);
  const small = fullHtml.length < DATA_URL_MAX_CHARS;
  if (small && (await showInBrowser(`data:text/html;charset=utf-8,${encodeURIComponent(fullHtml)}`))) return;
  const fileUri = await writeHtmlPreviewFile(fullHtml);
  if (await showInBrowser(fileUri)) return;
  await shareLocalFile(fileUri, { title, mimeType: HTML_MIME_TYPE });
}

/**
 * Share rendered HTML as a file through the system share sheet; static view only. A
 * dismissed sheet is not a failure; anything else is thrown for the caller to report.
 */
export async function shareHtmlPreview(html: string, title: string): Promise<void> {
  const fileUri = await writeHtmlPreviewFile(htmlExportDocument(html));
  await shareLocalFile(fileUri, { title, mimeType: HTML_MIME_TYPE });
}
