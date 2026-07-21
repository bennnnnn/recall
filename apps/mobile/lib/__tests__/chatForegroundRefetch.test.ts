import { shouldRefetchChatOnForeground } from "@/lib/chatForegroundRefetch";

describe("shouldRefetchChatOnForeground", () => {
  const base = {
    appState: "active" as const,
    token: "tok",
    chatId: "chat-1",
    streaming: false,
    chatLoading: false,
  };

  it("refetches when returning to an open idle chat", () => {
    expect(shouldRefetchChatOnForeground(base)).toBe(true);
  });

  it("skips while a stream is still active", () => {
    expect(shouldRefetchChatOnForeground({ ...base, streaming: true })).toBe(false);
  });

  it("skips when there is no open chat", () => {
    expect(shouldRefetchChatOnForeground({ ...base, chatId: null })).toBe(false);
  });

  it("skips background / inactive transitions", () => {
    expect(shouldRefetchChatOnForeground({ ...base, appState: "background" })).toBe(false);
    expect(shouldRefetchChatOnForeground({ ...base, appState: "inactive" })).toBe(false);
  });

  it("skips while the initial chat load is in flight", () => {
    expect(shouldRefetchChatOnForeground({ ...base, chatLoading: true })).toBe(false);
  });
});
