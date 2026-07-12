import {
  cacheDirectory,
  writeAsStringAsync,
  EncodingType,
} from "expo-file-system/legacy";
import * as WebBrowser from "expo-web-browser";
import { Linking, Platform, Share } from "react-native";
import { stripScripts } from "@/lib/previewSandbox";

/** Wrap bare HTML into a full document for browser rendering. */
export function wrapFullDocument(html: string): string {
  if (/^\s*<!DOCTYPE/i.test(html) || /^\s*<html/i.test(html)) {
    return html;
  }
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 16px; line-height: 1.5; color: #111827; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0; }
  td, th { border: 1px solid #E5E7EB; padding: 8px; }
  th { background: #F1F5F9; font-weight: 600; }
  pre { background: #F1F5F9; padding: 12px; border-radius: 8px; overflow-x: auto; }
  code { font-family: 'SF Mono', monospace; font-size: 14px; }
  img { max-width: 100%; }
</style>
</head>
<body>
${html}
</body>
</html>`;
}

/** HTML body suitable for react-native-render-html (no document shell). */
export { htmlForInlinePreview, previewHasVisibleText } from "@/lib/htmlForInlinePreview";

export function looksLikeInteractiveHtml(html: string): boolean {
  return /<\s*script\b/i.test(html);
}

export async function writeHtmlPreviewFile(html: string): Promise<string | null> {
  const dir = cacheDirectory;
  if (!dir) return null;

  const fileUri = `${dir}recall-preview-${Date.now()}.html`;
  try {
    await writeAsStringAsync(fileUri, html, {
      encoding: EncodingType.UTF8,
    });
    return fileUri;
  } catch {
    return null;
  }
}

/** Open rendered HTML in the system browser (works in Expo Go).

The system browser runs `<script>` unsandboxed, so model-generated JS is stripped
first — this path is a static view only. Interactive previews run in the in-app
WebView (CSP-sandboxed) instead. */
export async function openHtmlInBrowser(html: string): Promise<boolean> {
  const fullHtml = wrapFullDocument(stripScripts(html));

  if (fullHtml.length < 120_000) {
    const dataUrl = `data:text/html;charset=utf-8,${encodeURIComponent(fullHtml)}`;
    try {
      await Linking.openURL(dataUrl);
      return true;
    } catch {
      try {
        await WebBrowser.openBrowserAsync(dataUrl);
        return true;
      } catch {
        /* fall through */
      }
    }
  }

  const fileUri = await writeHtmlPreviewFile(fullHtml);
  if (!fileUri) return false;

  try {
    await Linking.openURL(fileUri);
    return true;
  } catch {
    /* fall through */
  }

  try {
    await WebBrowser.openBrowserAsync(fileUri);
    return true;
  } catch {
    /* try next */
  }

  if (Platform.OS === "ios" || Platform.OS === "android") {
    try {
      await Share.share(
        Platform.OS === "ios"
          ? { url: fileUri, title: "HTML Preview" }
          : { message: fileUri, title: "HTML Preview" },
      );
      return true;
    } catch {
      return false;
    }
  }

  return false;
}

/** Share rendered HTML via the system share sheet (scripts stripped — static view only). */
export async function shareHtmlPreview(html: string): Promise<boolean> {
  const fullHtml = wrapFullDocument(stripScripts(html));
  const fileUri = await writeHtmlPreviewFile(fullHtml);

  if (fileUri) {
    try {
      await Share.share(
        Platform.OS === "ios"
          ? { url: fileUri, title: "HTML Preview" }
          : { message: fileUri, title: "HTML Preview" },
      );
      return true;
    } catch {
      /* fall through */
    }
  }

  if (fullHtml.length < 120_000) {
    try {
      await Share.share({ message: fullHtml, title: "HTML Preview" });
      return true;
    } catch {
      return false;
    }
  }

  return false;
}

/** @deprecated use openHtmlInBrowser */
export async function openHtmlPreview(html: string): Promise<boolean> {
  return openHtmlInBrowser(html);
}
