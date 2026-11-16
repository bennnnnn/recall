// A formula wider than the line, inside a sentence: "Caffeine is C₈H₁₀N₄O₂, so adding the
// atomic masses: $8(12.011) + … = 194.19\ \text{g/mol}$ ☕" showed "adding the atomic
// masses: ☕" on the phone (live, 2026-11-15). The formula scrolled sideways in a
// ScrollView, and a View in a sentence's Text is what iOS lays out as 0×0. In a sentence it
// now wraps with the words, as it does alone on its line.
import { render } from "@testing-library/react-native";
import { Dimensions } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { formulaMayScroll } from "@/components/rich/mathColumn";
import { readLine, type Element } from "@/components/__tests__/support/mathInk";

jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: "LinkPreviewCard" }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@/components/WebPreviewCodeBlock", () => ({ WebPreviewCodeBlock: "WebPreviewCodeBlock" }));
jest.mock("@/components/rich/CircularClockBlock", () => ({ CircularClockBlock: "CircularClockBlock" }));

const SUM = String.raw`8(12.011) + 10(1.008) + 4(14.007) + 2(15.999) = 96.088 + 10.08 + 56.028 + 31.998 = 194.19\ \text{g/mol}`;
const SHOWN = "8(12.011) + 10(1.008) + 4(14.007) + 2(15.999) = 96.088 + 10.08 + 56.028 + 31.998 = 194.19 g/mol";

type Node = { type: unknown; parent: Node | null };

function insideText(node: Node): boolean {
  for (let up = node.parent; up; up = up.parent) {
    if (up.type === "Text") return true;
  }
  return false;
}

describe("a formula wider than the line", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 440, height: 956, scale: 3, fontScale: 1 });
  });
  afterEach(() => jest.restoreAllMocks());

  it.each([
    ["an emoji", " ☕"],
    ["words", " in all."],
  ])("in a sentence, followed by %s, is drawn in the sentence, never in a scroller", async (_name, after) => {
    const view = await render(
      <MarkdownContent content={`Caffeine is C₈H₁₀N₄O₂, so adding the atomic masses: $${SUM}$${after}`} />,
    );
    for (const scroller of view.queryAllByTestId("math-text-scroll") as unknown as Node[]) {
      expect(insideText(scroller)).toBe(false);
    }
    expect(readLine(view.toJSON() as unknown as Element)).toContain(`${SHOWN}${after}`);
  });

  it("alone on its line, is drawn whole and never in a scroller inside the line's Text", async () => {
    const view = await render(<MarkdownContent content={`So:\n\n$${SUM}$`} />);
    for (const scroller of view.queryAllByTestId("math-text-scroll") as unknown as Node[]) {
      expect(insideText(scroller)).toBe(false);
    }
    // Laid out as a calculation: the sum, then the total, a line each.
    const shown = readLine(view.toJSON() as unknown as Element);
    expect(shown).toContain("2(15.999) = 96.088 + 10.08 + 56.028 + 31.998");
    expect(shown).toContain("2(15.999) = 194.19 g/mol");
  });

  // Every way a sentence can hold one (PR #2467 review): in bold, beside a display formula
  // (`\sum` sends the paragraph to the display layout), in a list item.
  it.each([
    ["bold", `Adding them: **$${SUM}$** in all.`],
    ["beside a display formula", String.raw`Since $\sum_{i=1}^{4} n_i A_i$ adds them: ` + `$${SUM}$ ☕`],
    ["a list item", `- Adding the masses: $${SUM}$ ☕`],
  ])("in %s, is never in a scroller inside a Text", async (_name, content) => {
    const view = await render(<MarkdownContent content={content} />);
    for (const scroller of view.queryAllByTestId("math-text-scroll") as unknown as Node[]) {
      expect(insideText(scroller)).toBe(false);
    }
    expect(readLine(view.toJSON() as unknown as Element)).toContain("31.998");
  });

  it("is judged once for its width, and again for another width", () => {
    expect(formulaMayScroll(SUM, 18)).toBe(true);
    expect(formulaMayScroll(SUM, 18)).toBe(true);
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 2400, height: 956, scale: 3, fontScale: 1 });
    expect(formulaMayScroll(SUM, 18)).toBe(false);
  });
});
