import { MESSAGE_MAX_CHARS, messageChars, messageTooLong } from "@/features/chat/model/messageLimit";

describe("the longest message a turn takes", () => {
  it("counts the draft as it is sent: trimmed", () => {
    expect(messageTooLong(`  ${"a".repeat(MESSAGE_MAX_CHARS)}\n\n`)).toBe(false);
    expect(messageTooLong("a".repeat(MESSAGE_MAX_CHARS + 1))).toBe(true);
  });

  it("counts an emoji once, as the API does", () => {
    const emoji = "😀".repeat(MESSAGE_MAX_CHARS);
    expect(emoji.length).toBe(MESSAGE_MAX_CHARS * 2);
    expect(messageChars(emoji)).toBe(MESSAGE_MAX_CHARS);
    expect(messageTooLong(emoji)).toBe(false);
    expect(messageTooLong(`${emoji}a`)).toBe(true);
  });
});
