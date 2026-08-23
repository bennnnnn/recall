import { conversationMarkdownBody } from "@/lib/chatTranscript";
import type { Message } from "@/lib/api";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
}));

describe("conversationMarkdownBody", () => {
  it("joins user and assistant turns and skips system messages", () => {
    const body = conversationMarkdownBody([
      { id: "s1", role: "system", content: "hidden" },
      { id: "u1", role: "user", content: "hello" },
      { id: "a1", role: "assistant", content: "hi there" },
    ] as Message[]);
    expect(body).toContain("**share.role_user:**\nhello");
    expect(body).toContain("**share.role_assistant:**\nhi there");
    expect(body).not.toContain("hidden");
  });
});
