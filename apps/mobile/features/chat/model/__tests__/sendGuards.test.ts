jest.mock("@/features/attachments/model/attachments", () => ({
  messageTextForSend: (text: string) => text.trim(),
}));

import { canSend } from "@/features/chat/model/sendGuards";

const ready = {
  sendInFlight: false,
  chatLoading: false,
  chatId: "c1",
  isOffline: false,
  streaming: false,
  text: "hello",
  hasAttachment: false,
  token: "t",
  creating: false,
  attachPicking: false,
};

describe("canSend", () => {
  it("sends a ready message", () => {
    expect(canSend(ready)).toBe("send");
  });

  it("holds a send while the day's free messages are used up, silently: the banner says why", () => {
    expect(canSend({ ...ready, quotaBlocked: true })).toBe("blocked");
  });

  it("still names being offline first", () => {
    expect(canSend({ ...ready, quotaBlocked: true, isOffline: true })).toBe("offline");
  });
});
