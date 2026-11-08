// Inline maths followed by punctuation drew a gap before it on the phone: a follow-up
// "What if $v_0 = 15\text{ m/s}$?" read "…15 m/s ?", and a Given line read "20 m/s , g = …".
// A formula with a script is a View, and its box took the estimated width as a floor. The
// estimate ran about 6 px past the glyphs (a 0.33 em space where KaTeX_Main draws 0.25, an
// upright s at 0.52 em where it draws 0.394), and that room sat before the mark. A reply
// paragraph hid it: it draws a closing mark inside the formula, so the room fell after it.
import { render, type RenderResult } from "@testing-library/react-native";
import { Dimensions } from "react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { RichMathBody } from "@/components/rich/RichMathBody";
import { drawnBox, readLine, type Element } from "@/components/__tests__/support/mathInk";

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

const MARKS = ["?", ",", ".", "!", ";", ":", ")"] as const;

/** Every formula box on screen is as wide as its glyphs: nothing runs on past the last one. */
function expectNoRoomAfterGlyphs(view: RenderResult): void {
  const boxes = view.getAllByTestId("math-text-tall") as unknown as Element[];
  expect(boxes.length).toBeGreaterThan(0);
  for (const box of boxes) {
    const { box: drawn, ink } = drawnBox(box);
    expect(drawn).toBeCloseTo(ink, 1);
  }
}

function lineOf(view: RenderResult, testID: string, index = 0): string {
  return readLine(view.getAllByTestId(testID)[index] as unknown as Element);
}

describe("punctuation right after inline maths", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 440, height: 956, scale: 3, fontScale: 1 });
  });
  afterEach(() => jest.restoreAllMocks());

  it.each(MARKS)("sits against the formula in rich-card text (follow-ups, steps, callouts): %s", async (mark) => {
    const content = mark === ")"
      ? String.raw`(at $v_0 = 15\text{ m/s}$)`
      : String.raw`Take $v_0 = 15\text{ m/s}$${mark}`;
    const view = await render(<RichMathBody content={content} />);
    expect(lineOf(view, "rich-math-body")).toBe(mark === ")" ? "(at v₀ = 15 m/s)" : `Take v₀ = 15 m/s${mark}`);
    expectNoRoomAfterGlyphs(view);
  });

  it.each(MARKS)("sits against the formula in a reply paragraph, with one word gap after it: %s", async (mark) => {
    const content = mark === ")"
      ? String.raw`It falls (with $g = 9.81\text{ m/s}^2$) to the ground.`
      : String.raw`It falls with $g = 9.81\text{ m/s}^2$${mark} Then it lands.`;
    const view = await render(<MarkdownContent content={content} />);
    expect(lineOf(view, "md-math-inline-wrap")).toBe(mark === ")"
      ? "It falls (with g = 9.81 m/s²) to the ground."
      : `It falls with g = 9.81 m/s²${mark} Then it lands.`);
    expectNoRoomAfterGlyphs(view);
  });

  it("sits against the formula in a list item", async () => {
    const view = await render(<MarkdownContent content={String.raw`- With $v_0 = 15\text{ m/s}$, it rises 11.5 m.`} />);
    expect(readLine(view.toJSON() as unknown as Element)).toContain("With v₀ = 15 m/s, it rises 11.5 m.");
    expectNoRoomAfterGlyphs(view);
  });

  it("sits against the formula at the end of the user's own message", async () => {
    const view = await render(<MarkdownContent content={String.raw`What if $g$ was $10\text{ m/s}^2$?`} compact />);
    expect(lineOf(view, "md-math-inline-wrap")).toBe("What if g was 10 m/s²?");
    expectNoRoomAfterGlyphs(view);
  });

  it("sets a Given line's comma against its value", async () => {
    const content = ["**Given**  ", String.raw`$v_0 = 20\,\mathrm{m/s}$, $g = 10\,\mathrm{m/s}^2$`].join("\n");
    const view = await render(<MarkdownContent content={content} />);
    expect(lineOf(view, "workout-line")).toBe("v₀ = 20 m/s, g = 10 m/s²");
    expectNoRoomAfterGlyphs(view);
  });

  it("sets a comma against a fraction, which scrolls in its own viewport", async () => {
    const content = ["**Given**  ", String.raw`$a = \frac{1}{2}$, $t = 4\text{ s}$`].join("\n");
    const view = await render(<MarkdownContent content={content} />);
    expect(view.getByTestId("math-text-scroll")).toBeOnTheScreen();
    expect(lineOf(view, "workout-line")).toContain(", t = 4 s");
    expectNoRoomAfterGlyphs(view);
  });
});
