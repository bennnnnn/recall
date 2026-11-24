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
