export type GmailSyncResult = {
  status: string;
  message_count: number;
  reminders_created: number;
  skipped?: boolean;
};

export type GmailSyncMessage =
  | { key: "settings.gmail_sync_skipped" }
  | { key: "settings.gmail_sync_done"; params: { count: number } };

export function gmailSyncMessage(result: GmailSyncResult): GmailSyncMessage {
  if (result.skipped || result.status === "skipped") {
    return { key: "settings.gmail_sync_skipped" };
  }
  return { key: "settings.gmail_sync_done", params: { count: result.message_count } };
}
