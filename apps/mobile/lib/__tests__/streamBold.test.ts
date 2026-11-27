import { closeOpenBold } from "@/lib/markdown/streamBold";
import { markdownItInstance } from "@/lib/markdown/parser";

/** What markdown-it draws as plain text: a literal asterisk would be in it. */
function plainText(markdown: string): string {
  return markdownItInstance
    .parse(markdown, {})
    .filter((token) => token.type === "inline")
    .flatMap((token) => token.children ?? [])
    .filter((child) => child.type === "text")
    .map((child) => child.content)
    .join("");
}

describe("closeOpenBold", () => {
  it.each([
    ["a name being typed", "1. **Demo", "1. **Demo**"],
    ["an emoji-led name", "2. 🏛️ **Repub", "2. 🏛️ **Repub**"],
    ["half a closer", "1. **Democracy*", "1. **Democracy**"],
    ["a name with a space typed after it", "1. **Direct ", "1. **Direct** "],
    ["a bold phrase in a sentence", "Governments differ in **who holds", "Governments differ in **who holds**"],
    ["bold and italic", "***Note", "***Note***"],
    ["a bold-italic closer two stars in", "***Note**", "***Note***"],
    ["a closer after punctuation", "**Tip:", "**Tip:**"],
    ["a member's name", "    - **Physics", "    - **Physics**"],
  ])("closes %s", (_name, typing, drawn) => {
    expect(closeOpenBold(typing)).toBe(drawn);
    expect(plainText(closeOpenBold(typing))).not.toContain("*");
  });

  it.each([
    ["an opener with nothing after it yet", "1. **", "1. "],
    ["an emoji and an opener", "1. 🏛️ **", "1. 🏛️ "],
    ["the first star of an opener", "1. *", "1. "],
    ["a new opener after a closed name", "1. **Name** — and **", "1. **Name** — and "],
    ["a star after a space inside a bold", "**Tip: 2 *", "**Tip: 2** "],
    ["an opener after code", "Run `a ** b` and **", "Run `a ** b` and "],
  ])("holds back %s", (_name, typing, drawn) => {
    expect(closeOpenBold(typing)).toBe(drawn);
  });

  it.each([
    ["a closed name", "1. **Democracy** — power rests"],
    ["a bullet", "- item"],
    ["a multiplication", "2 * 3 = 6"],
    ["a footnote star", "Price 5*"],
    ["stars inside code", "Run `a ** b` now"],
    ["an escaped star", "Use \\*\\*bold\\*\\* in Markdown"],
    ["stars with spaces round them", "a ** b"],
    // A code span still typing runs to the line's end, as markdown-it will read it once closed.
    ["a code span still typing", "Use `**kw"],
    ["a formula in code still typing", "`x**2 + 1"],
    // Between two word characters: no partner yet, and the settled line draws it as typed.
    ["a power written with stars", "2**10 = 1024"],
    ["a power still typing", "2**"],
    ["no line yet", ""],
  ])("leaves %s as it is", (_name, typing) => {
    expect(closeOpenBold(typing)).toBe(typing);
  });

  // Every prefix of a line, as the stream shows it: never an asterisk on screen.
  it.each([
    "**Tip: 2 *really* helps**",
    "***Note*** read this first.",
    "1. 🏛️ **Republic** — the head of state is elected.",
    "    - **Direct democracy**: citizens vote on laws.",
  ])("draws no asterisk at any point of %j", (line) => {
    for (let end = 1; end <= line.length; end += 1) {
      const drawn = plainText(closeOpenBold(line.slice(0, end)));
      if (drawn.includes("*")) throw new Error(`"*" drawn for ${JSON.stringify(line.slice(0, end))}: ${drawn}`);
    }
  });

  it("reads only the line still typing", () => {
    expect(closeOpenBold("**Open above\n1. **Demo")).toBe("**Open above\n1. **Demo**");
    expect(closeOpenBold("1. **Done**\n")).toBe("1. **Done**\n");
  });
});
