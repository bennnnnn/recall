/**
 * The lines a chat carries when it leaves the app, as text or as a PDF: what it came from,
 * and where its reader gets the app (the user, 2026-11-18: a share converted no one). The
 * link is the build's `shareUrl` (a redirect on our own domain to the right store) marked
 * `ref=share`, so installs from shares can be counted; a build without one names the app only.
 */
import i18n from "@/lib/i18n";
import { config } from "@/lib/config";

/** `url` with `ref=share`, or null when it is no http(s) link. */
export function shareLink(url: string | null): string | null {
  if (!url) return null;
  try {
    const link = new URL(url);
    if (link.protocol !== "https:" && link.protocol !== "http:") return null;
    link.searchParams.set("ref", "share");
    return link.toString();
  } catch {
    return null;
  }
}

/** The footer's lines: where the chat came from, and the link when the build has one. */
export function shareFooterLines(url: string | null = config.shareUrl): string[] {
  const app = i18n.t("app.name");
  const link = shareLink(url);
  return [
    i18n.t("share.footer_from", { app }),
    ...(link ? [i18n.t("share.footer_get", { url: link })] : []),
  ];
}

/** The footer as plain text after a transcript, set apart by a rule. */
export function withShareFooter(text: string, url: string | null = config.shareUrl): string {
  return `${text.trimEnd()}\n\n—\n${shareFooterLines(url).join("\n")}`;
}
