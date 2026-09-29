import { render } from "@testing-library/react-native";

import { AnswerBlock } from "@/components/rich/AnswerBlock";

jest.mock("@/components/rich/MathText", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return {
    MathText: ({ latex }: { latex: string }) => <RNText testID="math-text">{latex}</RNText>,
  };
});

jest.mock("@/components/rich/MathSvgView", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return {
    MathSvgView: () => <RNText testID="math-svg">svg</RNText>,
  };
});

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { text?: string }) =>
      key === "rich.answer_a11y" && opts?.text != null ? `Answer: ${opts.text}` : key,
  }),
}));

describe("AnswerBlock chemistry notation", () => {
  it("renders the formula as text and does not typeset it", async () => {
    const formula = "M(H2O) = 18.015 g/mol";
    const { getByTestId, getByText, queryByTestId } = await render(
      <AnswerBlock content={`notation: chemistry\n${formula}`} />,
    );
    expect(getByTestId("answer-literal").props.children).toBe(formula);
    expect(getByText(formula)).toBeTruthy();
    expect(queryByTestId("math-text")).toBeNull();
    expect(queryByTestId("math-svg")).toBeNull();
    expect(getByTestId("answer-success-check")).toBeTruthy();
  });
});
