import { gmailSyncMessage } from "@/lib/gmailSyncFeedback";

describe("gmailSyncMessage", () => {
  it("returns skipped copy when the server throttles sync", () => {
    expect(
      gmailSyncMessage({
        status: "skipped",
        message_count: 0,
        reminders_created: 0,
        skipped: true,
      }),
    ).toEqual({ key: "settings.gmail_sync_skipped" });
  });

  it("returns success copy with message count", () => {
    expect(
      gmailSyncMessage({
        status: "ok",
        message_count: 12,
        reminders_created: 2,
        skipped: false,
      }),
    ).toEqual({ key: "settings.gmail_sync_done", params: { count: 12 } });
  });
});
