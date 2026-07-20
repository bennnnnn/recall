import {
  displayChatTitle,
  sanitizeManualChatTitle,
} from "@/lib/chatTitle";

const t = (key: string) =>
  ({
    "common.untitled": "Untitled",
    "chat.title_generating": "Generating title…",
  })[key] ?? key;

describe("chatTitle", () => {
  it("displayChatTitle prefers stored title", () => {
    expect(displayChatTitle("Python tips", {}, t)).toBe("Python tips");
  });

  it("displayChatTitle shows generating placeholder", () => {
    expect(displayChatTitle(null, { generating: true }, t)).toBe("Generating title…");
  });

  it("displayChatTitle falls back to untitled", () => {
    expect(displayChatTitle(null, {}, t)).toBe("Untitled");
  });

  it("sanitizeManualChatTitle strips quotes and enforces length", () => {
    expect(sanitizeManualChatTitle('  "My chat"  ')).toBe("My chat");
    expect(sanitizeManualChatTitle('"My Trip Plan".')).toBe("My Trip Plan");
    expect(sanitizeManualChatTitle("New chat")).toBe("New chat");
    expect(sanitizeManualChatTitle("   ")).toBeNull();
    expect(sanitizeManualChatTitle("x".repeat(81))).toBeNull();
  });

  it("displayChatTitle unwraps dirty stored titles", () => {
    expect(displayChatTitle('"My Trip Plan".', {}, t)).toBe("My Trip Plan");
  });
});
