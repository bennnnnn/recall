import {
  displayLang,
  groupTokensByLine,
  isHtmlFenceLang,
  looksLikeHtmlPage,
  normalizeLang,
  parseFenceLang,
  shouldUseHtmlPreview,
} from "@/lib/codeHighlight";

describe("parseFenceLang", () => {
  it("lowercases and strips trailing fence metadata", () => {
    expect(parseFenceLang("TypeScript")).toBe("typescript");
    expect(parseFenceLang("js {highlight}")).toBe("js");
    expect(parseFenceLang("  ")).toBe("");
  });
});

describe("normalizeLang", () => {
  it("maps aliases to their Prism grammar key", () => {
    expect(normalizeLang("ts")).toBe("typescript");
    expect(normalizeLang("py")).toBe("python");
    expect(normalizeLang("")).toBe("");
  });

  it("passes through unknown languages unchanged", () => {
    expect(normalizeLang("cobol")).toBe("cobol");
  });
});

describe("displayLang", () => {
  it("hides generic/plain badges", () => {
    expect(displayLang("")).toBe("");
    expect(displayLang("plain")).toBe("");
    expect(displayLang("text")).toBe("");
    expect(displayLang("clike")).toBe("");
  });

  it("shows real language badges lowercased", () => {
    expect(displayLang("Python")).toBe("python");
  });
});

describe("isHtmlFenceLang", () => {
  it("recognizes html/htm/markup", () => {
    expect(isHtmlFenceLang("html")).toBe(true);
    expect(isHtmlFenceLang("HTM")).toBe(true);
    expect(isHtmlFenceLang("markup")).toBe(true);
    expect(isHtmlFenceLang("javascript")).toBe(false);
  });
});

describe("looksLikeHtmlPage", () => {
  it("detects a doctype page", () => {
    expect(looksLikeHtmlPage("<!DOCTYPE html><html></html>")).toBe(true);
  });

  it("rejects plain text", () => {
    expect(looksLikeHtmlPage("just some text")).toBe(false);
  });
});

describe("shouldUseHtmlPreview", () => {
  it("is true for an explicit html fence", () => {
    expect(shouldUseHtmlPreview("html", "<div>hi</div>")).toBe(true);
  });

  it("is false for an explicit non-html language even with angle brackets", () => {
    expect(shouldUseHtmlPreview("jsx", "<div>hi</div>")).toBe(false);
  });

  it("sniffs an untagged fence that looks like a full HTML page", () => {
    expect(shouldUseHtmlPreview("", "<!DOCTYPE html><html><body>hi</body></html>")).toBe(true);
  });
});

describe("groupTokensByLine", () => {
  it("splits multi-line token text across line groups", () => {
    const lines = groupTokensByLine([{ text: "a\nb", color: "#000" }]);
    expect(lines).toEqual([[{ text: "a", color: "#000" }], [{ text: "b", color: "#000" }]]);
  });

  it("returns a single empty line for empty input", () => {
    expect(groupTokensByLine([])).toEqual([[]]);
  });
});
