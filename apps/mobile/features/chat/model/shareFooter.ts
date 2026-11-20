/**
 * The lines a chat carries when it leaves the app, as text or as a PDF: what it came from,
 * and where its reader gets the app (the user, 2026-11-18: a share converted no one). The
 * link is the build's `shareUrl` (a redirect on our own domain to the right store) marked
 * `ref=share`, so installs from shares can be counted; a build without one names the app only.
 */
import i18n from "@/lib/i18n";
import { config } from "@/lib/config";

/**
 * `url` with `ref=share` (any `ref` it had is replaced: the share is what is counted), or
 * null when it is no https link. A value that is set but unusable ("recall.com/get", with no
 * scheme) says so in development, where a release would ship without its link.
 */
export function shareLink(url: string | null): string | null {
  if (!url) return null;
  try {
    const link = new URL(url);
    if (link.protocol !== "https:") throw new Error("not https");
    link.searchParams.set("ref", "share");
    return link.toString();
  } catch {
    if (typeof __DEV__ !== "undefined" && __DEV__) {
      console.warn(`EXPO_PUBLIC_SHARE_URL is no https link, so shares carry none: ${url}`);
    }
    return null;
  }
}

/**
 * The footer's lines: where the chat came from, and the link when the build has one.
 * `asLink` writes the link for its medium: a PDF's must be a markdown link to be tapped.
 */
export function shareFooterLines(
  url: string | null = config.shareUrl,
  asLink: (link: string) => string = (link) => link,
): string[] {
  const app = i18n.t("app.name");
  const link = shareLink(url);
  return [
    i18n.t("share.footer_from", { app }),
    ...(link ? [i18n.t("share.footer_get", { url: asLink(link) })] : []),
  ];
}

/** The footer as plain text after a transcript, set apart by a rule. */
export function withShareFooter(text: string, url: string | null = config.shareUrl): string {
  return `${text.trimEnd()}\n\n—\n${shareFooterLines(url).join("\n")}`;
}
