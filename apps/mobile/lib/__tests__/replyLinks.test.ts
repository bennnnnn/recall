/**
 * A reply's links as the phone reads them: a name still marked to look up is drawn as its words
 * until the server places it (apps/api `reply_links.py`).
 */
import { isNameMark, repairBrokenMarkdownLinks } from "@/lib/markdown/replyLinks";

describe("isNameMark", () => {
  it("reads the server's mark, with or without a city", () => {
    expect(isNameMark("check")).toBe(true);
    expect(isNameMark("check:Z%C3%BCrich")).toBe(true);
    expect(isNameMark(" CHECK ")).toBe(true);
  });

  it("reads no other target as a mark", () => {
    expect(isNameMark("checkout.html")).toBe(false);
    expect(isNameMark("https://www.google.com/search?q=check")).toBe(false);
  });
});

describe("repairBrokenMarkdownLinks", () => {
  it("repairs broken markdown links with dollar delimiters", () => {
    const broken = "1. [CODE Salon]$https://www.yelp.com/biz/code-salon$ — Top-rated";
    expect(repairBrokenMarkdownLinks(broken)).toBe("1. [CODE Salon](https://www.yelp.com/biz/code-salon) — Top-rated");
  });

  it("does not merge adjacent inline math spans into a broken link", () => {
    // `[0,2]$ \times $` once became `[0,2]( \times )`, leaking the `$` delimiters.
    const math = "Integrate 9 over $x \\in [0,2]$ \\times $y \\in [1,3]$:";
    expect(repairBrokenMarkdownLinks(math)).toBe(math);
  });

  it("still repairs a www. url without an explicit scheme", () => {
    expect(repairBrokenMarkdownLinks("[Google]$www.google.com$")).toBe("[Google](www.google.com)");
  });
});
