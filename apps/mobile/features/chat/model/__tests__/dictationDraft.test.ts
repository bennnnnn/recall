import {
  dictationAnchor,
  draftWithDictation,
} from "@/features/chat/model/dictationDraft";

describe("where dictated words go in the draft", () => {
  it("goes at the caret, with a space on each side where the text needs one", () => {
    const anchor = dictationAnchor("Dear Sam,Thanks.", { start: 9, end: 9 });
    expect(draftWithDictation(anchor, "see you at noon")).toBe("Dear Sam, see you at noon Thanks.");
  });

  it("adds no space before punctuation or after a space already there", () => {
    const anchor = dictationAnchor("Hello .", { start: 6, end: 6 });
    expect(draftWithDictation(anchor, "world")).toBe("Hello world.");
  });

  it("keeps a selection's text and puts the words after it", () => {
    const anchor = dictationAnchor("keep this", { start: 0, end: 4 });
    expect(draftWithDictation(anchor, "and")).toBe("keep and this");
  });

  it("follows the draft when the field was not being edited, as before", () => {
    expect(draftWithDictation(dictationAnchor("  draft  ", null), "more")).toBe("draft more");
    expect(draftWithDictation(dictationAnchor("", null), "hello")).toBe("hello");
  });

  it("leaves the draft exactly as it was while nothing has been heard", () => {
    const anchor = dictationAnchor("draft \n", { start: 7, end: 7 });
    expect(draftWithDictation(anchor, "   ")).toBe("draft \n");
  });

  it("treats a caret outside the draft as none", () => {
    expect(draftWithDictation(dictationAnchor("abc", { start: 9, end: 9 }), "d")).toBe("abc d");
  });
});
