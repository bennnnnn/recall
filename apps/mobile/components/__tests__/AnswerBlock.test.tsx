import { render } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

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

describe("AnswerBlock", () => {
  beforeEach(() => {
    mockFormula.mockClear();
  });

  it("keeps light finals on MathText (no KaTeX WebView)", async () => {
    const { getByLabelText } = await render(<AnswerBlock content={String.raw`x = \pm 2`} />);
    expect(getByLabelText("Answer: x = ± 2")).toBeOnTheScreen();
    expect(mockFormula).not.toHaveBeenCalled();
  });

  it("BUG FIX regression: two roots joined with or stay on MathText so the last root is not clipped", async () => {
    const { getByLabelText } = await render(
      <AnswerBlock content={String.raw`x = \frac{1}{2} \text{ or } x = 3`} />,
    );
    expect(getByLabelText(/x = 3/)).toBeOnTheScreen();
    expect(mockFormula).not.toHaveBeenCalled();
  });

  it("keeps both T05 solution branches reachable at their normal math size", async () => {
    const latex = String.raw`x = 2 \pi k + \frac{\pi}{6} \text{ or } x = 2 \pi k + \frac{5 \pi}{6},\quad k \in \mathbb{Z}`;
    const { getByTestId, getAllByTestId, getByLabelText } = await render(<AnswerBlock content={latex} />);
    expect(getByLabelText(/Answer: x = 2 π k.*or.*k ∈ ℤ/)).toBeOnTheScreen();
    expect(getAllByTestId("math-text-tall")).toHaveLength(2);
    for (const index of [0, 1]) {
      const viewport = getByTestId(`answer-line-scroll-${index}`);
      expect(viewport.props.horizontal).toBe(true);
      expect(viewport.props.showsHorizontalScrollIndicator).toBe(true);
      expect(StyleSheet.flatten(viewport.props.style).alignSelf).toBe("stretch");
      expect(StyleSheet.flatten(viewport.props.contentContainerStyle).minWidth).toBe("100%");
    }
    expect(mockFormula).not.toHaveBeenCalled();
  });

  it("provides horizontal overflow for a long native answer without an OR separator", async () => {
    const latex = String.raw`x = \frac{1}{2} + \frac{3}{4} + \frac{5}{6} + \frac{7}{8} + \frac{9}{10}`;
    const { getByTestId, queryByTestId } = await render(<AnswerBlock content={latex} />);
    expect(getByTestId("answer-line-scroll-0").props.horizontal).toBe(true);
    expect(queryByTestId("answer-line-scroll-1")).toBeNull();
    expect(mockFormula).not.toHaveBeenCalled();
  });

  it("BUG FIX regression: strips a streaming ``` closer leaked into the answer body", async () => {
    const { queryByText } = await render(
      <AnswerBlock content={"x = -2 or x = 2\n```"} />,
    );
    expect(queryByText("```")).toBeNull();
    expect(queryByText(/x = -2/)).toBeOnTheScreen();
  });

  it("routes heavy \\begin{…} answers to stretch displayMode KaTeX (never compact)", async () => {
    const latex = String.raw`\begin{cases} x = 1 \\ y = 2 \end{cases}`;
    await render(<AnswerBlock content={latex} />);
    expect(mockFormula).toHaveBeenCalledTimes(1);
    const props = mockFormula.mock.calls[0][0];
    expect(props.displayMode).toBe(true);
    expect(props.compact).toBeUndefined();
    expect(props.latex).toBe(latex);
  });

  it("BUG FIX regression: a \\sqrt answer hosts MathText as a direct View (not clipped by a Text)", async () => {
    // iOS clips a View nested inside a Text to the line box — the radicand's
    // bottom (the digit under √) was cut off in this gray box. A sqrt must
    // render inside the answerRow View, never wrapped in a Text.
    const { getByTestId } = await render(
      <AnswerBlock content={String.raw`2\sqrt{2}`} />,
    );
    expect(getByTestId("answer-row")).toBeOnTheScreen();
    expect(getByTestId("math-sqrt-radicand")).toBeOnTheScreen();
    expect(mockFormula).not.toHaveBeenCalled();
  });

  it("uses KaTeX for heavy answers when only expo-dom WebView is available (Expo Go)", async () => {
    const latex = String.raw`\begin{matrix}a&b\\c&d\end{matrix}`;
    await render(<AnswerBlock content={latex} />);
    expect(mockFormula).toHaveBeenCalled();
  });
});
