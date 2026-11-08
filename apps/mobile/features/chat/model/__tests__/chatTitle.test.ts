import {
  chatNeedsGeneratedTitle,
  displayChatTitle,
  provisionalAttachmentTitle,
  provisionalChatTitle,
  sanitizeManualChatTitle,
} from "@/features/chat/model/title";

const t = (key: string) =>
  ({
    "common.untitled": "Untitled",
    "chat.title_generating": "Generating title…",
    "chat.title_image": "Image",
    "chat.title_file": "File",
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

  it("chatNeedsGeneratedTitle treats placeholders as missing", () => {
    expect(chatNeedsGeneratedTitle(null)).toBe(true);
    expect(chatNeedsGeneratedTitle("Untitled")).toBe(true);
    expect(chatNeedsGeneratedTitle("Homework")).toBe(false);
  });

  it("provisionalChatTitle uses the first line and truncates", () => {
    expect(provisionalChatTitle("What's still open for me to finish tonight?", t)).toBe(
      "What's still open for me to finish tonight",
    );
    expect(provisionalChatTitle("  Hello\nsecond line", t)).toBe("Hello");
    expect(provisionalChatTitle("   ", t)).toBeNull();
    expect(provisionalChatTitle("x".repeat(60), t)).toBe(`${"x".repeat(47)}…`);
    expect(
      provisionalChatTitle(
        "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
        t,
      ),
    ).toBe("Image");
    expect(provisionalChatTitle("[File: notes.pdf]", t)).toBe("File");
    expect(provisionalChatTitle("What's in this image?\n\n[Image: local]", t)).toBe(
      "Image",
    );
  });

  it("provisionalAttachmentTitle is Image/File only", () => {
    expect(provisionalAttachmentTitle("hi", t)).toBeNull();
    expect(provisionalAttachmentTitle("good morning", t)).toBeNull();
    expect(
      provisionalAttachmentTitle(
        "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
        t,
      ),
    ).toBe("Image");
    expect(provisionalAttachmentTitle("[File: notes.pdf]", t)).toBe("File");
  });

  // A photo-only first turn was titled "Image" in every language.
  it("titles an attachment-only first turn in the app's language", () => {
    const de = (key: string) => ({ "chat.title_image": "Bild", "chat.title_file": "Datei" })[key] ?? key;
    expect(provisionalAttachmentTitle("[Image: local]", de)).toBe("Bild");
    expect(provisionalAttachmentTitle("[File: notes.pdf]", de)).toBe("Datei");
  });

  // A rename to `Meeting with "Bob"` was saved as `Meeting with "Bob`.
  it.each([
    ['Meeting with "Bob"', 'Meeting with "Bob"'],
    ["Meeting with \u201cBob\u201d", "Meeting with \u201cBob\u201d"],
    ['"Bob" and "Alice"', '"Bob" and "Alice"'],
    ['"Say "hi""', 'Say "hi"'],
    ["'Bob's plan'", "Bob's plan"],
    ["Rock 'n' roll", "Rock 'n' roll"],
    ['"Trip plan', "Trip plan"],
    ['Trip plan"', "Trip plan"],
    ['"Meeting with "Bob"', 'Meeting with "Bob"'],
  ])("keeps quotes inside a title, strips only wrapping or stray ones: %s", (raw, kept) => {
    expect(sanitizeManualChatTitle(raw)).toBe(kept);
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
