// "The balanced equation is $2H_2 + O_2 \rightarrow 2H_2O$. This means…" drew
// "→ 2H₂O.This means" on the phone, and "…$ shows that" drew "2H₂Oshows". The
// formula's box took its estimated width as a fixed size; "→" measured 0.7 em
// against KaTeX's 1 em, so the glyphs ran past the box into the word gap.
import { render, within, type RenderResult } from "@testing-library/react-native";
import { Dimensions, StyleSheet, type ViewStyle } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { drawnBox, type Element } from "@/components/__tests__/support/mathInk";

jest.mock("@/components/LinkPreviewCard", () => ({
  LinkPreviewCard: "LinkPreviewCard",
}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("@/components/WebPreviewCodeBlock", () => ({
  WebPreviewCodeBlock: "WebPreviewCodeBlock",
}));
jest.mock("@/components/rich/CircularClockBlock", () => ({
  CircularClockBlock: "CircularClockBlock",
}));
jest.mock("@/components/rich/AnswerBlock", () => ({
  AnswerBlock: "AnswerBlock",
}));

const BALANCED = String.raw`The balanced equation is $2H_2 + O_2 \rightarrow 2H_2O$. This means 1 mole of $H_2$ produces 1 mole of $H_2O$.`;
const REACTION = String.raw`The reaction $2H_2 + O_2 \rightarrow 2H_2O$ shows that 2 moles of hydrogen make 2 moles of water.`;

const SUBSCRIPT: Record<string, string> = Object.fromEntries(
  Array.from("0123456789").map((digit, i) => [digit, String.fromCharCode(0x2080 + i)]),
);
const SUPERSCRIPT: Record<string, string> = {
  0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹",
};

type Node = { type?: string; props?: Record<string, unknown>; children?: unknown } | string | null;

function styleOf(node: Node): ViewStyle {
  if (!node || typeof node === "string") return {};
  return StyleSheet.flatten(node.props?.style as ViewStyle) ?? {};
}

/** How far a script Text is moved off the baseline (down is positive). */
function scriptShift(style: ViewStyle): number {
  const steps = Array.isArray(style.transform) ? (style.transform as { translateY?: unknown }[]) : [];
  const shift = steps.find((step) => typeof step.translateY === "number")?.translateY;
  return typeof shift === "number" ? shift : 0;
}

/**
 * The line as a reader sees it: each item's glyphs, a dropped script as a
 * subscript, and a space wherever an item keeps a word gap after it.
 */
function visibleText(node: unknown): string {
  if (node == null) return "";
  if (typeof node === "string") return node.replace(/ /g, " ");
  if (Array.isArray(node)) return node.map(visibleText).join("");
  const element = node as Exclude<Node, string | null>;
  // The caret and the empty run a formula sets its baseline with draw no glyphs.
  if (element.props?.testID === "stream-caret" || element.props?.testID === "math-baseline") return "";
  const style = styleOf(element);
  let text = visibleText(element.children);
  if (element.props?.testID === "math-script") {
    const table = scriptShift(style) > 0 ? SUBSCRIPT : SUPERSCRIPT;
    text = Array.from(text, (ch) => table[ch] ?? ch).join("");
  }
  const gap = typeof style.marginRight === "number" ? style.marginRight : 0;
  return gap > 0 ? `${text} ` : text;
}

/**
 * The formula's own box: as wide as its glyphs (measured from KaTeX's advances), never a
 * cap below them that they paint past, nor a floor that leaves room after them.
 */
function expectGlyphWideBox(view: RenderResult): void {
  const formula = view.getAllByTestId("math-text-tall")[0] as unknown as Element;
  const box = styleOf(formula as Node);
  expect(box.width).toBeUndefined();
  expect(box.minWidth).toBeUndefined();
  const { box: drawn, ink } = drawnBox(formula);
  expect(drawn).toBeCloseTo(ink, 1);
}

function rowText(view: RenderResult): string {
  return visibleText(view.getByTestId("md-math-inline-wrap")).trim().replace(/ {2,}/g, " ");
}

describe("the space after an inline formula", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
  });
  afterEach(() => jest.restoreAllMocks());

  it("keeps \"2H₂O. This\" after a reaction arrow and its full stop", async () => {
    const view = await render(<MarkdownContent content={BALANCED} />);
    expect(rowText(view)).toBe(
      "The balanced equation is 2H₂ + O₂ → 2H₂O. This means 1 mole of H₂ produces 1 mole of H₂O.",
    );
    expectGlyphWideBox(view);
  });

  it("keeps \"2H₂O shows\" after a reaction arrow", async () => {
    const view = await render(<MarkdownContent content={REACTION} />);
    expect(rowText(view)).toBe(
      "The reaction 2H₂ + O₂ → 2H₂O shows that 2 moles of hydrogen make 2 moles of water.",
    );
    expectGlyphWideBox(view);
    // The gap belongs to the formula's item, so the next word cannot touch it.
    const formula = view.getByTestId("math-text-tall");
    expect(styleOf(formula.parent as unknown as Node).marginRight).toBeGreaterThan(0);
    expect(within(formula).queryByText("shows")).toBeNull();
  });

  it("keeps the space after a comma that closes on the formula", async () => {
    const view = await render(
      <MarkdownContent content={String.raw`Burn it: $CH_4 + 2O_2 \rightarrow CO_2 + 2H_2O$, which releases heat.`} />,
    );
    expect(rowText(view)).toBe("Burn it: CH₄ + 2O₂ → CO₂ + 2H₂O, which releases heat.");
    expectGlyphWideBox(view);
  });

  it.each([
    ["a list item", `- ${REACTION}`],
    ["a bold sentence", `**The reaction $2H_2 + O_2 \\rightarrow 2H_2O$ shows that** 2 moles react.`],
    ["a quote", `> ${REACTION}`],
  ])("keeps \"2H₂O shows\" in %s", async (_host, content) => {
    const view = await render(<MarkdownContent content={content} />);
    expect(visibleText(view.toJSON()).replace(/ {2,}/g, " ")).toContain("2H₂O shows that");
    expectGlyphWideBox(view);
  });

  it("keeps the space while the reply streams and once it settles", async () => {
    const partial = String.raw`The balanced equation is $2H_2 + O_2 \rightarrow 2H_2O$. This means`;
    const streaming = await render(<MarkdownContent content={partial} streaming />);
    expect(visibleText(streaming.toJSON())).toContain("2H₂O. This means");
    expectGlyphWideBox(streaming);
    await streaming.rerender(<MarkdownContent content={BALANCED} />);
    expect(rowText(streaming)).toContain("2H₂O. This means 1 mole");
  });

  it("keeps the space after a formula wide enough to scroll", async () => {
    const wide = String.raw`C_6H_{12}O_6 + 6O_2 \rightarrow 6CO_2 + 6H_2O + C_6H_{12}O_6 + 6O_2 \rightarrow 6CO_2 + 6H_2O`;
    const view = await render(<MarkdownContent content={`Twice over: $${wide}$ shows the cycle.`} />);
    const scroller = view.getByTestId("math-text-scroll");
    expect(within(scroller).getByTestId("math-text-tall")).toBeOnTheScreen();
    expect(styleOf(scroller as unknown as Node).marginRight ?? styleOf(scroller.parent as unknown as Node).marginRight)
      .toBeGreaterThan(0);
    expect(rowText(view)).toMatch(/6H₂O shows the cycle\.$/);
    expectGlyphWideBox(view);
  });

  it("keeps the space after an arrow drawn inside the line of text", async () => {
    const view = await render(<MarkdownContent content={String.raw`Then $A \rightarrow B$ shows the path.`} />);
    expect(visibleText(view.toJSON())).toContain("A → B shows the path.");
  });
});
