import { render } from "@testing-library/react-native";

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
