import { shareFooterLines, shareLink, withShareFooter } from "@/features/chat/model/shareFooter";

jest.mock("@/lib/config", () => ({ config: { shareUrl: null } }));

describe("share footer", () => {
  it("names the app and links to it, marked as a share", () => {
    expect(shareFooterLines("https://example.com/get")).toEqual([
      "Shared from Recall, the AI chat that remembers you.",
      "Get the app: https://example.com/get?ref=share",
    ]);
  });

  it("keeps the link's own query", () => {
    expect(shareLink("https://example.com/get?lang=de")).toBe("https://example.com/get?lang=de&ref=share");
  });

  it("names the app only when the build has no link, or no https link", () => {
    expect(shareFooterLines(null)).toEqual(["Shared from Recall, the AI chat that remembers you."]);
    expect(shareLink("javascript:alert(1)")).toBeNull();
    expect(shareLink("recall.com/get")).toBeNull();
    expect(shareLink("http://example.com/get")).toBeNull();
  });

  it("replaces a ref the link had: the share is what is counted", () => {
    expect(shareLink("https://example.com/get?ref=ad")).toBe("https://example.com/get?ref=share");
  });

  it("writes the link for its medium", () => {
    expect(shareFooterLines("https://example.com/get", (link) => `[${link}](${link})`)[1]).toBe(
      "Get the app: [https://example.com/get?ref=share](https://example.com/get?ref=share)",
    );
  });

  it("ends a transcript after a rule", () => {
    expect(withShareFooter("# Chat\n\nYou: hi\n\n", "https://example.com/get")).toBe(
      "# Chat\n\nYou: hi\n\n—\nShared from Recall, the AI chat that remembers you.\n" +
        "Get the app: https://example.com/get?ref=share",
    );
  });
});
