import {
  displayLang,
  groupTokensByLine,
  isHtmlFenceLang,
  looksLikeHtmlPage,
  normalizeLang,
  parseFenceLang,
  resolveTokenColor,
  shouldUseHtmlPreview,
  TOKEN_COLORS,
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

describe("resolveTokenColor", () => {
  it("returns the color unchanged in light mode", () => {
    expect(resolveTokenColor(TOKEN_COLORS.keyword, false)).toBe(TOKEN_COLORS.keyword);
  });

  it("remaps every light token color to its dark counterpart in dark mode", () => {
    for (const [key, light] of Object.entries(TOKEN_COLORS)) {
      const dark = resolveTokenColor(light, true);
      expect(dark).not.toBe(light);
      expect(dark).toMatch(/^#[0-9a-fA-F]{6}$/);
      // Every key must resolve (no light color should fall through unchanged).
      expect(dark).not.toBe(light);
      void key;
    }
  });

  it("falls back to the input color for unrecognized values", () => {
    expect(resolveTokenColor("#abcdef", true)).toBe("#abcdef");
    expect(resolveTokenColor("#abcdef", false)).toBe("#abcdef");
  });

  it("remaps the near-black plain token so code is visible on a dark panel", () => {
    expect(resolveTokenColor(TOKEN_COLORS.plain, true)).toBe("#E6E6E6");
  });
});
