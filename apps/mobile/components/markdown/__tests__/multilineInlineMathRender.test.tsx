import { render } from "@testing-library/react-native";

import { nestedAccessibleElements } from "@/components/__tests__/a11yTree";
import { MarkdownContent } from "@/components/MarkdownContent";

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
jest.mock("react-native-webview", () => {
  throw new Error("react-native-webview native module is not linked (test)");
});
jest.mock("@expo/dom-webview", () => {
  throw new Error("@expo/dom-webview native module is not linked (test)");
});
jest.mock("@/components/CodeBlock", () => {
  const { Text: RNText } = jest.requireActual("react-native");
  return {
    CodeBlock: ({ code, lang }: { code: string; lang: string }) => (
      <RNText>{`${lang}:${code}`}</RNText>
    ),
  };
});

const C04_RESPONSE = "The partial derivative of \\(x^2 y\\) with respect to \\(y\\) is:  \n**\\(x^2\\)**  \n\n### Explanation\n- When differentiating with respect to \\(y\\), treat \\(x\\) as a constant.  \n- The derivative of \\(y\\) (with respect to \\(y\\)) is 1, so:  \n  \\(\n  \\frac{\\partial}{\\partial y}(x^2 y) = x^2 \\cdot 1 = x^2.\n  \\)";

describe('C04 multiline inline math rendering', () => {
  it.each([false, true])('typesets the exact saved C04 list formula with streaming=%s', async (streaming) => {
    const { getAllByLabelText, getAllByTestId, getAllByText, queryByText, toJSON } = await render(
      <MarkdownContent content={C04_RESPONSE} streaming={streaming} />,
    );
    expect(getAllByTestId("math-frac").length).toBeGreaterThanOrEqual(1);
    expect(getAllByText("∂").length).toBeGreaterThanOrEqual(2);
    expect(getAllByText("∂ y").length).toBeGreaterThanOrEqual(2);
    // The formula's line is the screen-reader element and reads it in words;
    // its scroller is no second TalkBack stop inside it.
    expect(getAllByTestId("math-text-scroll").every((node) => node.props.accessible === false)).toBe(true);
    const line = getAllByLabelText(/∂ over ∂ y, \(x squared y\) = x squared dot 1/);
    expect(line.length).toBeGreaterThanOrEqual(1);
    expect(line[0]!.props.accessible).toBe(true);
    expect(nestedAccessibleElements(toJSON())).toEqual([]);
    expect(queryByText(/\\frac|\\partial|\$/)).toBeNull();
  });
});
