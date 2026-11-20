import { memorySourceChatHref, stripMemoryAsOf } from "@/features/memory/model/memoryFacts";

describe("memoryFacts", () => {
  it("drops the server's freshness stamp from a fact", () => {
    expect(stripMemoryAsOf("As of 2026-09-20: Likes short answers")).toBe("Likes short answers");
    expect(stripMemoryAsOf("  Likes tea ")).toBe("Likes tea");
  });

  it("opens a fact's chat at the message that states it", () => {
    expect(
      memorySourceChatHref({ source_chat_id: "c1", source_chat_title: "Trip", source_message_id: "m1" }),
    ).toEqual({ pathname: "/", params: { chatId: "c1", returnTo: "memory", highlightMessage: "m1" } });
  });

  it("opens the chat alone when the message is not known", () => {
    expect(
      memorySourceChatHref({ source_chat_id: "c1", source_chat_title: "Trip", source_message_id: null }),
    ).toEqual({ pathname: "/", params: { chatId: "c1", returnTo: "memory" } });
  });

  it.each([
    // A deleted chat clears the fact's chat id (SET NULL): nothing to open.
    [{ source_chat_id: null, source_chat_title: null }],
    [{ source_chat_id: undefined, source_chat_title: "Trip" }],
    // The page shows no "From" line without a title, so it opens nothing either.
    [{ source_chat_id: "c1", source_chat_title: null }],
  ])("has no link without a chat to open: %j", (fact) => {
    expect(memorySourceChatHref(fact)).toBeNull();
  });
});
