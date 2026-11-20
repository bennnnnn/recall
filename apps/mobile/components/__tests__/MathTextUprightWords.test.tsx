/**
 * Words in a text group stay words wherever the group sits. A part of `\frac`, `\sqrt` or a
 * script is read again by its own nested parse, which once read the group's words as maths a
 * second time: "moved" became a run inside the run, whose private-use start marker iOS drew as
 * a 👕 emoji, and "by" fell into the maths italic (phone, 2026-11-18):
 * `$VR = \frac{\text{distance moved by effort}}{\text{distance moved by load}}$`.
 */
import { render } from "@testing-library/react-native";

import { MarkdownContent } from "@/components/MarkdownContent";
import { MathText } from "@/components/rich/MathText";
import { latexToSvgMath } from "@/lib/math/svgMath";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));
// Display maths drawn by the native fallback, the renderer that painted the emoji.
const mockDisplayMaths: string[] = [];
jest.mock("@/components/rich/MathSvgView", () => {
  const React = jest.requireActual("react");
  const { MathText: NativeMath } = jest.requireActual("@/components/rich/MathText");
  return {
    MathSvgView: ({ latex }: { latex: string }) => {
      mockDisplayMaths.push(latex);
      return React.createElement(NativeMath, { latex });
    },
  };
});

const VELOCITY_RATIO = String.raw`VR = \frac{\text{distance moved by effort}}{\text{distance moved by load}}`;
// A private-use marker, an emoji, or a variation selector that asks for one.
const NOT_TEXT = /[-️]|\p{Extended_Pictographic}/u;

type Rendered = Awaited<ReturnType<typeof render>>;
type Node = ReturnType<Rendered["getByTestId"]>;

/** The characters a node draws, read through every nested text. */
function drawn(node: Node | string): string {
  return typeof node === "string" ? node : node.children.map(drawn).join("");
}

/** A run's words. Maths draws its spaces as no-break spaces, so a run never wraps inside;
 * any other character in a gap (a marker, an emoji) is left for the comparison to catch. */
function uprightRuns(screen: Rendered): string[] {
  return screen.queryAllByTestId("math-upright-run").map((node) => drawn(node).replace(/\u00A0/g, " "));
}

function italicLetters(screen: Rendered): string[] {
  return screen.queryAllByTestId("math-variable").map(drawn);
}

function expectWords(screen: Rendered, words: string[], variables: string[]): void {
  expect(JSON.stringify(screen.toJSON())).not.toMatch(NOT_TEXT);
  expect(uprightRuns(screen)).toEqual(words);
  expect(italicLetters(screen)).toEqual(variables);
}

describe("words in a text group inside maths", () => {
  beforeEach(() => {
    mockDisplayMaths.length = 0;
  });

  it("draws the velocity ratio's words upright with plain spaces, inline", async () => {
    const screen = await render(<MarkdownContent content={`So ${"$"}${VELOCITY_RATIO}${"$"} here.`} />);
    expectWords(screen, ["distance moved by effort", "distance moved by load"], ["VR"]);
  });

  it("draws the velocity ratio's words upright with plain spaces, as a line of its own", async () => {
    const screen = await render(
      <MarkdownContent content={`The velocity ratio is\n\n${"$"}${VELOCITY_RATIO}${"$"}\n\nso it is 4.`} />,
    );
    expectWords(screen, ["distance moved by effort", "distance moved by load"], ["VR"]);
  });

  it("draws the velocity ratio's words upright as display maths", async () => {
    const screen = await render(<MarkdownContent content={`${"$$"}${VELOCITY_RATIO}${"$$"}`} />);
    expect(mockDisplayMaths).not.toEqual([]);
    expectWords(screen, ["distance moved by effort", "distance moved by load"], ["VR"]);
  });

  it("sets the words as MathJax text in display maths", async () => {
    const svg = (await latexToSvgMath(VELOCITY_RATIO, true))?.svg ?? "";
    expect(svg).toContain('data-mml-node="mtext"');
    expect(svg).not.toMatch(NOT_TEXT);
  });

  it.each([
    ["a fraction", String.raw`\frac{\text{work done by effort}}{\text{time it takes}}`, ["work done by effort", "time it takes"], []],
    ["a root", String.raw`\sqrt{\text{area of the square}}`, ["area of the square"], []],
    ["a subscript", String.raw`v_{\text{speed of the car}}`, ["speed of the car"], ["v"]],
    ["a superscript", String.raw`e^{\text{rate times time}}`, ["rate times time"], ["e"]],
    ["a script's text group", String.raw`t_\text{time to the top}`, ["time to the top"], ["t"]],
    ["a fraction's roman group", String.raw`\frac{\mathrm{mass\ of\ the\ load}}{\mathrm{volume}}`, ["mass of the load", "volume"], []],
    ["a fraction's text group with a sentence word", String.raw`\frac{\text{distance so far}}{\text{time}}`, ["distance so far", "time"], []],
    ["a nested fraction", String.raw`\frac{1}{\frac{\text{output from the machine}}{\text{input}}}`, ["output from the machine", "input"], []],
  ])("keeps the words of %s upright", async (_where, latex, words, variables) => {
    const screen = await render(<MathText latex={latex} />);
    expectWords(screen, words, variables);
  });

  it.each([
    [String.raw`\text{a b}`, ["a b"]],
    [String.raw`\mathrm{a\ b}`, ["a b"]],
    [String.raw`\frac{\text{a b}}{2}`, ["a b"]],
    [String.raw`\frac{\text{cost per hour}}{2}`, ["cost per hour"]],
    [String.raw`\frac{\text{A \& B}}{2}`, ["A & B"]],
    [String.raw`\sqrt{\text{it's here}}`, ["it's here"]],
    [String.raw`\text{work done}^2`, ["work done"]],
  ])("draws %s as its words, upright", async (latex, words) => {
    const screen = await render(<MathText latex={latex} />);
    expectWords(screen, words, []);
  });

  it("draws no private-use marker or emoji beside an operator name", async () => {
    const screen = await render(
      <MathText latex={String.raw`\frac{\operatorname{lcm}(a, b)}{\text{least common multiple of}}`} />,
    );
    expect(JSON.stringify(screen.toJSON())).not.toMatch(NOT_TEXT);
    expect(uprightRuns(screen)).toContain("least common multiple of");
  });
});
