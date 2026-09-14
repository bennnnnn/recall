import { Message } from "@/lib/api";
import i18n from "@/lib/i18n";

/** Markdown body of a chat (no title heading) — used by share and PDF export. */
export function conversationMarkdownBody(messages: Message[]): string {
  return messages
    .filter((m) => m.role !== "system")
    .map((m) =>
      m.role === "user"
        ? `**${i18n.t("share.role_user")}:**\n${m.content}`
        : `**${i18n.t("share.role_assistant")}:**\n${m.content}`,
    )
    .join("\n\n");
}

/** Full markdown transcript including a title heading. */
export function conversationTranscript(title: string | null, messages: Message[]): string {
  const header = `# ${title?.trim() || i18n.t("share.default_title")}\n\n`;
  return header + conversationMarkdownBody(messages);
}
