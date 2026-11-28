import { markdownItInstance } from "@/lib/markdown/parser";
import { hideUnpairedMarkers } from "@/lib/markdown/streamMarkers";

const HOLD = "\u200b";
/** The caret's mark (`STREAM_CARET`, components/StreamingCursor.tsx), which this project cannot load. */
const STREAM_CARET = "\uE010";

type Drawn = { text: string; bold: string[]; italic: string[]; code: string[]; listItems: number };

/** What markdown-it draws for a line: its plain text, its bold and italic runs, its code. */
function drawn(markdown: string): Drawn {
  const tokens = markdownItInstance.parse(markdown, {});
  const out: Drawn = { text: "", bold: [], italic: [], code: [], listItems: 0 };
  for (const block of tokens) {
    if (block.type === "list_item_open") out.listItems += 1;
    if (block.type !== "inline") continue;
    let into: "bold" | "italic" | null = null;
    for (const child of block.children ?? []) {
      if (child.type === "strong_open") into = "bold";
      else if (child.type === "em_open") into = "italic";
      else if (child.type === "strong_close" || child.type === "em_close") into = null;
      else if (child.type === "code_inline") out.code.push(child.content);
      else if (child.type === "text") {
        out.text += child.content;
        if (into) out[into].push(child.content);
      }
    }
  }
  return out;
}

/** As the stream shows it: the line still typing, then the caret after it. */
const shown = (typing: string) => hideUnpairedMarkers(typing) + STREAM_CARET;

describe("hideUnpairedMarkers", () => {
  it.each([
    ["a name being typed", "1. **Demo", "1. Demo"],
    ["an emoji-led name", "2. 🏛️ **Repub", "2. 🏛️ Repub"],
    ["half a closer", "1. **Democracy*", "1. Democracy"],
    ["a whole closer that has not met its next character", "1. **Democracy**", "1. Democracy"],
    ["a name ending in a colon", "**Given:**", `Given:`],
    ["a bold phrase in a sentence", "Governments differ in **who holds", "Governments differ in who holds"],
    ["bold and italic", "***Note", `Note`],
    ["a bold-italic closer two stars in", "***Note**", `Note`],
    ["a member's name", "    - **Physics", "    - Physics"],
    ["an opener with nothing after it yet", "1. **", "1. "],
    ["the first star of an opener", "1. *", "1. "],
    ["a new opener after a closed name", "1. **Name** — and **", "1. **Name** — and "],
    ["a star after a space inside a bold", "**Tip: 2 *", `Tip: 2 `],
    ["an italic opened inside a bold", "**Tip: 2 *really", `Tip: 2 really`],
    ["a bold before a code span still typing", "**Run `npm i", `Run \`npm i`],
    ["a code name in bold, its tick still open", "1. **`useSt", "1. `useSt"],
    ["an opener the line may never close", "Use **kwargs to pass named arguments", "Use kwargs to pass named arguments"],
    ["a step heading still typing", "**1. Subtract 4", `${HOLD}1. Subtract 4`],
  ])("leaves out %s", (_name, typing, expected) => {
    expect(hideUnpairedMarkers(typing)).toBe(expected);
    expect(drawn(shown(typing)).text).not.toContain("*");
  });

  it.each([
    ["a closed name and its text", "1. **Democracy** — power rests"],
    ["a closed name in code and its text", "1. **`useState`** — holds a value"],
    ["a bullet", "- item"],
    ["a bullet written with a star", "* item"],
    ["a multiplication", "2 * 3 = 6"],
    ["stars with spaces round them", "a ** b"],
    ["a power written with stars", "2**10 = 1024"],
    ["an escaped star", "Use \\*\\*bold\\*\\* in Markdown"],
    ["stars inside closed code", "Run `a ** b` now"],
    ["a code span still typing", "Use `**kw"],
    ["a formula in code still typing", "`x**2 + 1"],
    ["no line yet", ""],
  ])("leaves %s as it is", (_name, typing) => {
    expect(hideUnpairedMarkers(typing)).toBe(typing);
  });

  it("never draws a numbered list or a step out of a step heading still typing", () => {
    const line = drawn(shown("**1. Subtract 4"));
    expect(line.listItems).toBe(0);
    expect(line.bold).toEqual([]);
  });

  it("draws bold only what the finished line draws bold", () => {
    // An opener with no partner is literal once the line ends: never bold while it types.
    const settled = drawn("Use **kwargs to pass named arguments\n");
    expect(settled.bold).toEqual([]);
    for (const end of [8, 14, 30]) {
      expect(drawn(shown("Use **kwargs to pass named arguments".slice(0, end))).bold).toEqual([]);
    }
  });

  // Every prefix of a line, with the caret after it as the stream draws it: never an asterisk.
  it.each([
    "**Tip: 2 *really* helps**",
    "***Note*** read this first.",
    "1. 🏛️ **Republic** — the head of state is elected.",
    "    - **Direct democracy**: citizens vote on laws.",
    "**Given:** a mass of 2 kg",
    "1. **`useState`** — holds a value between renders",
    "**Run `npm install`** first, then **start**.",
    "**1. Subtract 4 from both sides** — Subtraction property of equality",
    "Use **kwargs to pass named arguments, and **args for the rest",
  ])("draws no asterisk at any point of %j", (line) => {
    const settledStars = drawn(`${line}\n`).text.split("*").length - 1;
    for (let end = 1; end <= line.length; end += 1) {
      const prefix = line.slice(0, end);
      const text = drawn(shown(prefix)).text;
      // A star the finished line draws (an opener with no partner) may show once the line has it all.
      if (text.includes("*") && end < line.length) throw new Error(`"*" drawn for ${JSON.stringify(prefix)}: ${text}`);
      if (end === line.length) expect(text.split("*").length - 1).toBeLessThanOrEqual(settledStars);
    }
  });

  it("reads only the line still typing", () => {
    expect(hideUnpairedMarkers("**Open above\n1. **Demo")).toBe("**Open above\n1. Demo");
    expect(hideUnpairedMarkers("1. **Done**\n")).toBe("1. **Done**\n");
  });
});
