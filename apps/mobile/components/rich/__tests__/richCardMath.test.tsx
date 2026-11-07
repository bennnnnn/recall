import { fireEvent, render } from "@testing-library/react-native";
import { Dimensions, StyleSheet } from "react-native";

import { nestedAccessibleElements } from "@/components/__tests__/a11yTree";
import { ArrayBlock } from "@/components/rich/ArrayBlock";
import { ChipText } from "@/components/rich/ChipText";
import { QuizCard } from "@/components/rich/QuizCard";
import { richTextLabel } from "@/components/rich/RichMathBody";
import { StepList } from "@/components/rich/StepList";
import { findLatexLeaks } from "@/lib/math/latexLeaks";
import { DYNAMIC_TYPE_MAX, Weight } from "@/lib/type";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
}));
jest.mock("@/lib/haptics", () => ({
  selection: jest.fn(),
  notifySuccess: jest.fn(),
  notifyWarning: jest.fn(),
}));
// Display maths draws through MathJax asynchronously; its own tests cover it.
jest.mock("@/components/rich/MathSvgView", () => {
  const React = jest.requireActual("react");
  const { MathText } = jest.requireActual("@/components/rich/MathText");
  return {
    MathSvgView: ({ latex }: { latex: string }) => React.createElement(MathText, { latex }),
  };
});

type Node = { type: string; props: Record<string, unknown>; children: (Node | string)[] | null };

/** Every string a reader sees, in order. */
function visible(node: Node | Node[] | string | null): string {
  if (node == null) return "";
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(visible).join("");
  return (node.children ?? []).map(visible).join("");
}

beforeEach(() => {
  jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
});
afterEach(() => jest.restoreAllMocks());

describe("steps draw their maths", () => {
  const STEPS = ["Add 9: $x^2+6x+9 = 16$", "So **x = 1** and `y = 2`", "Plain words only"];

  it("shows no LaTeX source and draws the maths as maths", async () => {
    const view = await render(<StepList steps={STEPS} />);
    const seen = visible(view.toJSON() as unknown as Node);
    expect(seen).not.toContain("$");
    expect(seen).not.toContain("^");
    expect(findLatexLeaks(seen)).toEqual([]);
    // The exponent is a raised script, not a caret.
    expect(view.getAllByText("2").length).toBeGreaterThan(0);
  });

  it("reads a step with maths as one VoiceOver element, in words", async () => {
    const view = await render(<StepList steps={STEPS} />);
    const row = view.getByTestId("rich-math-body");
    expect(row.props.accessible).toBe(true);
    expect(row.props.accessibilityRole).toBe("text");
    const label = row.props.accessibilityLabel as string;
    expect(label).toMatch(/^Add 9: x/);
    expect(label).toContain("= 16");
    expect(findLatexLeaks(label)).toEqual([]);
  });

  it("keeps bold, code, selectable text and the badge's text-size cap", async () => {
    const view = await render(<StepList steps={STEPS} />);
    expect(StyleSheet.flatten(view.getByText("x = 1").props.style)).toMatchObject(Weight.bold);
    expect(view.getByText("y = 2")).toBeOnTheScreen();
    expect(view.getByText("Add").props.selectable).toBe(true);
    expect(view.getByText("1").props.maxFontSizeMultiplier).toBe(DYNAMIC_TYPE_MAX);
  });

  it("puts the step's flex on the wrapping row, not on every word", async () => {
    const view = await render(<StepList steps={[STEPS[0]!]} />);
    expect(StyleSheet.flatten(view.getByTestId("rich-math-body").props.style)).toMatchObject({ flex: 1 });
    expect(StyleSheet.flatten(view.getByText("Add").props.style).flex).toBeUndefined();
  });
});

describe("quiz cards draw their maths", () => {
  const QUIZ = JSON.stringify({
    question: "What is $\\frac{1}{2} + \\frac{1}{4}$?",
    options: ["$\\frac{3}{4}$", "$x^2$", "`numbers[2]`"],
    answer: 0,
    explanation: "Add the quarters: $\\frac{2}{4} + \\frac{1}{4}$.",
  });

  it("shows no LaTeX source in the question, the options or the explanation", async () => {
    const view = await render(<QuizCard content={QUIZ} />);
    await fireEvent.press(view.getAllByTestId("rich-math-body")[1]!);
    await fireEvent.press(view.getByText("rich.quiz_check"));
    const seen = visible(view.toJSON() as unknown as Node);
    expect(seen).not.toContain("$");
    expect(seen).not.toContain("\\frac");
    expect(findLatexLeaks(seen)).toEqual([]);
    expect(view.getByText("rich.quiz_correct")).toBeOnTheScreen();
    // Rows that are their own element (the question, the explanation) read clean;
    // an option's row leaves its words to the radio.
    for (const row of view.getAllByTestId("rich-math-body")) {
      if (row.props.accessible) expect(findLatexLeaks(row.props.accessibilityLabel as string)).toEqual([]);
      else expect(row.props.accessibilityLabel).toBeUndefined();
    }
    for (const radio of view.getAllByRole("radio")) {
      expect(findLatexLeaks(radio.props.accessibilityLabel as string)).toEqual([]);
    }
  });

  it("says an option's maths as words on the radio itself, with nothing focusable inside it", async () => {
    const view = await render(<QuizCard content={QUIZ} />);
    const radios = view.getAllByRole("radio");
    expect(radios.map((radio) => radio.props.accessibilityLabel)).toEqual([
      richTextLabel("$\\frac{3}{4}$"),
      richTextLabel("$x^2$"),
      "numbers[2]",
    ]);
    for (const radio of radios.slice(0, 2)) {
      const label = radio.props.accessibilityLabel as string;
      expect(label.length).toBeGreaterThan(0);
      expect(label).not.toContain("$");
      expect(findLatexLeaks(label)).toEqual([]);
    }
    expect(radios[1]!.props.accessibilityLabel).toMatch(/x/);
    // TalkBack reads a parent's words only from children that are not focusable.
    expect(nestedAccessibleElements(view.toJSON())).toEqual([]);
  });

  it("keeps an option without maths as one chip text, and option words not selectable", async () => {
    const view = await render(<QuizCard content={QUIZ} />);
    expect(view.getByText("numbers[2]")).toBeOnTheScreen();
    const math = await render(<ChipText style={{}} chip={{}}>{"Pick $x$ now"}</ChipText>);
    expect(math.getByText("Pick").props.selectable).toBe(false);
  });
});

describe("an array card with maths in its line and note", () => {
  const ARRAY = JSON.stringify({
    name: "xs",
    title: "Squares of $n$: $n^2$",
    values: [1, 4, 9],
    caption: "3 values",
    note: "So **$x^2 = 9$** has two roots.",
  });

  it("is one element whose label reads its line, list, caption and note, maths as words", async () => {
    const view = await render(<ArrayBlock content={ARRAY} />);
    const card = view.getByTestId("array-block");
    const label = card.props.accessibilityLabel as string;
    expect(label).toBe(
      [richTextLabel("Squares of $n$: $n^2$"), "xs = [1, 4, 9]", "3 values", richTextLabel("So **$x^2 = 9$** has two roots.")].join(". "),
    );
    expect(label).not.toContain("$");
    expect(findLatexLeaks(label)).toEqual([]);
    expect(nestedAccessibleElements(view.toJSON())).toEqual([]);
  });
});
