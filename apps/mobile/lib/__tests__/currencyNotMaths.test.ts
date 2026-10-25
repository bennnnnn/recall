import { layoutCheckVerificationLines, preprocessMarkdown, splitInlineMath } from "@/lib/markdown/preprocess";
import { markdownItInstance } from "@/lib/markdown/parser";
import { restoreMathEscapes } from "@/lib/math/text";

/**
 * A dollar sign used as currency is text; a `$...$` pair is maths. Live on
 * 2026-10-25, "Half of $38.40 = $ 19.20" drew "38.40 =" in the maths font and
 * lost both dollars: the closing `$` had a space before it and an amount
 * after it, so it opened a price and closed nothing.
 */
function seen(markdown: string, presented = false) {
  const prepared = preprocessMarkdown(markdown, undefined, { presented });
  const math: string[] = [];
  let text = "";
  for (const block of markdownItInstance.parse(prepared, {})) {
    for (const token of block.children ?? []) {
      if (token.type === "text") {
        for (const part of splitInlineMath(token.content)) {
          if (part.type === "math") math.push(restoreMathEscapes(part.value));
          text += restoreMathEscapes(part.value);
        }
      } else if (token.type === "softbreak" || token.type === "hardbreak") {
        text += " ";
      }
    }
    if (block.type === "paragraph_close") text += "\n";
  }
  return { math, text: text.trim() };
}

/** Replies the server saved, exactly as stored. */
const STORED = [
  {
    source: "Half of $38.40 = $ 19.20, plus the $12 from last week = $ 31.20.",
    text: "Half of $38.40 = $ 19.20, plus the $12 from last week = $ 31.20.",
  },
  {
    source: "*   **Accommodation:** $50–$80/night for hostels or basic B&Bs = $ 350–$560 for 7 nights.",
    text: "Accommodation: $50–$80/night for hostels or basic B&Bs = $ 350–$560 for 7 nights.",
  },
  {
    source: "*   **Food:** $30/day for local spots, street food, and groceries = $ 210.",
    text: "Food: $30/day for local spots, street food, and groceries = $ 210.",
  },
];

describe("currency stays text", () => {
  it.each(STORED)("shows the stored reply as written: $source", ({ source, text }) => {
    for (const presented of [true, false]) {
      const view = seen(source, presented);
      expect(view.math).toEqual([]);
      expect(view.text).toBe(text);
    }
  });

  it.each([
    "$5 and $10",
    "It costs $1,200–$1,500.",
    "The total = $ 210",
    "That is $30/day.",
    "Rooms run $50–$80/night.",
    "Pick between $5 and $6.",
    "The house sold for $1.5M.",
    "If you save $20 a month = $240 a year.",
    "If you save $20 a month = $ 240 a year.",
    "Half of $38.40 = $19.20, plus the $12 from last week = $31.20.",
    "*   **Food:** $30/day for local spots, street food, and groceries = $210.",
    "Two rooms = $ 160 and three = $ 240.",
  ])("keeps every dollar of %s", (source) => {
    const view = seen(source);
    expect(view.math).toEqual([]);
    expect(view.text).toBe(source.replace(/^\*\s+\*\*(.+?)\*\*/, "$1"));
  });
});

describe("inline maths still renders", () => {
  it.each([
    ["$x^2$", ["x^2"]],
    ["$E = mc^2$", ["E = mc^2"]],
    [String.raw`$2H_2 + O_2 \rightarrow 2H_2O$`, [String.raw`2H_2 + O_2 \rightarrow 2H_2O`]],
    [String.raw`$\frac{1}{2}$`, [String.raw`\frac{1}{2}`]],
    ["$a = 3$ and $b = 4$", ["a = 3", "b = 4"]],
    [String.raw`$5 \times 3 = 15$`, [String.raw`5 \times 3 = 15`]],
    // Pandoc would leave this as text (a space before the closer); TeX draws
    // "x =", and the renderer keeps padded spans such as `$2 $`.
    ["Then $x = $", ["x ="]],
    ["$-3$", ["-3"]],
    ["The answer is $-3$.", ["-3"]],
    ["$3.5$", ["3.5"]],
    ["where $n$ is the number", ["n"]],
    ["$12 + 8 = 20$ dollars", ["12 + 8 = 20"]],
    ["$3 + 4 = 7$, so it costs $7.", ["3 + 4 = 7"]],
    [String.raw`It costs $5, and $4! = 4 \times 3 \times 2 \times 1 = 24$.`, [String.raw`4! = 4 \times 3 \times 2 \times 1 = 24`]],
  ])("draws %s as maths", (source, math) => {
    expect(seen(source).math).toEqual(math);
  });

  it.each([
    ["The cost $C = 5n$ dollars for $n$ items", ["C = 5n", "n"], "The cost C = 5n dollars for n items"],
    ["At $80/night for $n$ nights, the cost is $C = 80n$.", ["n", "C = 80n"], "At $80/night for n nights, the cost is C = 80n."],
    ["Budget $100 a week for $w$ weeks: $100w$.", ["w", "100w"], "Budget $100 a week for w weeks: 100w."],
    ["Rent is $1.5M and $x$ is the share.", ["x"], "Rent is $1.5M and x is the share."],
    ["Pay $30/day for food, then $x$ is left.", ["x"], "Pay $30/day for food, then x is left."],
  ])("keeps the price and the maths apart in %s", (source, math, text) => {
    const view = seen(source);
    expect(view.math).toEqual(math);
    expect(view.text).toBe(text);
  });
});

describe("a 'for' inside a sentence is no check label", () => {
  it.each([
    "*   **Food:** $30/day for local spots, street food, and groceries = $210.",
    "*   **Accommodation:** $80/night for hostels = $560 for 7 nights.",
    "The answer is x = 7. Never a ✓ for x = 6.",
    "For x = 3.",
  ])("adds no colon to %s", (line) => {
    expect(layoutCheckVerificationLines(line)).toBe(line);
  });

  it.each([
    ["- For $x = 2$", "- For $x = 2$:"],
    ["For F = 0", "For F = 0:"],
    ["1. **For** $x = 3$", "1. **For** $x = 3$:"],
    ["✓ For $x = -1$", "✓ For $x = -1$:"],
  ])("still closes the label %s", (line, label) => {
    expect(layoutCheckVerificationLines(line)).toBe(label);
  });
});
