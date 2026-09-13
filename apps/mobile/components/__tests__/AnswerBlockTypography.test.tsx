import { render } from "@testing-library/react-native";
import { Dimensions, StyleSheet } from "react-native";

import { MathText } from "@/components/rich/MathText";
import { AnswerBlock } from "@/components/rich/AnswerBlock";

const mockFormula = jest.fn((_props: Record<string, unknown>) => null);

jest.mock("@/components/rich/MathFormulaWebView", () => ({
  MathFormulaWebView: (props: Record<string, unknown>) => {
    mockFormula(props);
    return null;
  },
}));

jest.mock("@/lib/webView", () => ({
  getPreviewWebView: () => ({ mode: "expo-dom" }),
}));

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { text?: string }) =>
      key === "rich.answer_a11y" && opts?.text != null ? `Answer: ${opts.text}` : key,
  }),
}));


describe("standalone answer typography", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({
      width: 390, height: 844, scale: 3, fontScale: 1,
    });
    mockFormula.mockClear();
  });
  afterEach(() => jest.restoreAllMocks());

  it("renders the exact C12 fraction larger than ordinary inline math", async () => {
    const latex = String.raw`\frac{\pi^{2}}{6}`;
    const answer = await render(<AnswerBlock content={latex} />);
    expect(answer.getByText("π")).toHaveStyle({ fontSize: 17.5, lineHeight: 22.5 });
    expect(answer.getByText("²")).toHaveStyle({ fontSize: 17.5 });
    expect(answer.getByText("6")).toHaveStyle({ fontSize: 17.5 });
    expect(answer.getByTestId("math-frac")).toHaveStyle({ width: 40, height: 55 });
    expect(answer.getByTestId("math-text-tall")).toHaveStyle({ width: 47.5, height: 55 });
    expect(answer.getByLabelText("Answer: π^2/6")).toBeOnTheScreen();
    expect(mockFormula).not.toHaveBeenCalled();

    const inline = await render(<MathText latex={latex} />);
    expect(inline.getByText("π")).toHaveStyle({ fontSize: 14, lineHeight: 18 });
    expect(inline.getByTestId("math-frac")).toHaveStyle({ width: 32, height: 44 });
  });

  it("scales fractional exponents in the answer without shrinking their digits", async () => {
    const { getByText, getByTestId } = await render(<AnswerBlock content="9^{1/6}" />);
    expect(getByText("9")).toHaveStyle({ fontSize: 20 });
    expect(getByText("1/6")).toHaveStyle({ fontSize: 17.5, lineHeight: 22.5 });
    expect(getByTestId("math-text-tall")).toHaveStyle({ height: 37.5 });
    expect(getByTestId("math-fractional-sup")).toHaveStyle({ paddingBottom: 15 });
  });

  it("scales indexed roots and their radicands together", async () => {
    const { getByText, getByTestId } = await render(<AnswerBlock content={String.raw`\sqrt[6]{9}`} />);
    expect(getByText("6")).toHaveStyle({ fontSize: 15, lineHeight: 17.5 });
    expect(getByText("9")).toHaveStyle({ fontSize: 20, lineHeight: 25 });
    expect(getByTestId("math-text-tall")).toHaveStyle({ height: 32.5 });
  });

  it("keeps native fraction bounds proportional at larger accessibility text scale", async () => {
    jest.spyOn(Dimensions, "get").mockReturnValue({
      width: 390, height: 844, scale: 3, fontScale: 1.6,
    });
    const { getByTestId, getByText } = await render(<AnswerBlock content={String.raw`\frac{\pi^{2}}{6}`} />);
    expect(getByTestId("math-frac")).toHaveStyle({ width: 64, height: 88 });
    expect(getByTestId("math-text-tall")).toHaveStyle({ width: 76, height: 88 });
    // Native Text applies fontScale itself; the style must not multiply it twice.
    expect(getByText("6")).toHaveStyle({ fontSize: 17.5 });
    expect(getByTestId("answer-line-scroll-0").props.horizontal).toBe(true);
  });

  it.each([
    ["27", "27", 20],
    ["Value: $x^2$", "Value: x", 20],
    [String.raw`Area: $\frac{1}{2}$`, "1", 17.5],
  ] as const)(
    "uses the answer type scale across native content branches: %s", async (content, value, fontSize) => {
      const { getByText } = await render(<AnswerBlock content={content} />);
      expect(getByText(value)).toHaveStyle({ fontSize });
    },
  );

  it("retains horizontal overflow instead of reducing a long answer's type size", async () => {
    const content = String.raw`x = \frac{1}{2} + \frac{3}{4} + \frac{5}{6} + \frac{7}{8} + \frac{9}{10} + \frac{11}{12} + \frac{13}{14}`;
    const { getByTestId, getByText } = await render(<AnswerBlock content={content} />);
    expect(getByTestId("answer-line-scroll-0").props.horizontal).toBe(true);
    const bounds = StyleSheet.flatten(getByTestId("math-text-tall").props.style);
    expect(bounds.width).toBeGreaterThan(390);
    expect(bounds.flexShrink).toBe(0);
    expect(getByText("14")).toHaveStyle({ fontSize: 17.5 });
  });
});
