import { PASTE_MAX_CHARS } from "@/features/attachments/model/pastedText";
import {
  PASTE_ATTACH_MIN_CHARS,
  readComposerChange,
  readPastedText,
} from "@/features/chat/model/composerPaste";

jest.mock("expo-file-system", () => ({}));
jest.mock("expo-file-system/legacy", () => ({ cacheDirectory: "file:///cache/" }));

const words = (n: number) => "word ".repeat(Math.ceil(n / 5)).slice(0, n);

describe("a change to the composer, read as a paste or not", () => {
  it("leaves typing, autocorrect and a short paste to the field", () => {
    expect(readComposerChange("Hel", "Hello")).toEqual({ kind: "text" });
    expect(readComposerChange("teh cat", "the cat")).toEqual({ kind: "text" });
    expect(readComposerChange("", words(PASTE_ATTACH_MIN_CHARS))).toEqual({ kind: "text" });
    expect(readComposerChange("abc", "abc")).toEqual({ kind: "text" });
  });

  it("takes more than the threshold, in one change, as an attachment and keeps the draft", () => {
    const pasted = words(PASTE_ATTACH_MIN_CHARS + 1);
    expect(readComposerChange("Summarize: ", `Summarize: ${pasted}`)).toEqual({
      kind: "attach",
      text: pasted,
      remaining: "Summarize: ",
    });
    // In the middle of a draft: the text on both sides stays.
    expect(readComposerChange("before  after", `before ${pasted} after`)).toMatchObject({
      kind: "attach",
      remaining: "before  after",
    });
  });

  it("replaces a selection the paste went over, as the field would", () => {
    const pasted = `Q${words(PASTE_ATTACH_MIN_CHARS * 2)}`;
    expect(readComposerChange("keep SELECTED end", `keep ${pasted} end`)).toEqual({
      kind: "attach",
      text: pasted,
      remaining: "keep  end",
    });
  });

  it("refuses a paste longer than one may be and adds nothing", () => {
    expect(readComposerChange("draft", `draft${"x".repeat(PASTE_MAX_CHARS + 1)}`)).toEqual({ kind: "too_long" });
    expect(readComposerChange("", "x".repeat(PASTE_MAX_CHARS))).toMatchObject({ kind: "attach" });
  });

  it("reads the maths pad's Paste key the same way", () => {
    expect(readPastedText("x^2", "draft")).toEqual({ kind: "text" });
    expect(readPastedText("y".repeat(PASTE_ATTACH_MIN_CHARS + 1), "draft")).toMatchObject({
      kind: "attach",
      remaining: "draft",
    });
    expect(readPastedText("y".repeat(PASTE_MAX_CHARS + 1), "draft")).toEqual({ kind: "too_long" });
  });
});

describe("a paste that shares an edge with the draft", () => {
  const pasted = `${"Body text. ".repeat(250)}The end.`;

  it("is cut out by the selection it went over, all of it", () => {
    // Select all of "Please fix this." and paste a text that also ends in ".".
    expect(readComposerChange("Please fix this.", pasted, { start: 0, end: 16 })).toEqual({
      kind: "attach",
      text: pasted,
      remaining: "",
    });
  });

  it("keeps its first character when the text after the caret starts the same", () => {
    const paste = `b${"x".repeat(PASTE_ATTACH_MIN_CHARS)}`;
    expect(readComposerChange("ab", `a${paste}b`, { start: 1, end: 1 })).toEqual({
      kind: "attach",
      text: paste,
      remaining: "ab",
    });
  });

  it("falls back to matching the texts when the selection does not fit the change", () => {
    expect(readComposerChange("draft ", `draft ${pasted}`, { start: 99, end: 99 })).toMatchObject({
      kind: "attach",
      remaining: "draft ",
    });
  });

  it("counts characters as the API does: an emoji is one", () => {
    const emoji = "😀".repeat(PASTE_ATTACH_MIN_CHARS / 2 + 100);
    expect(emoji.length).toBeGreaterThan(PASTE_ATTACH_MIN_CHARS);
    expect(readComposerChange("", emoji)).toEqual({ kind: "text" });
    expect(readComposerChange("", "😀".repeat(PASTE_MAX_CHARS))).toMatchObject({ kind: "attach" });
  });
});
