import { fireEvent, render } from "@testing-library/react-native";

import { MathFormulaWebView } from "@/components/rich/MathFormulaWebView";

jest.mock("@/lib/webView", () => ({
  getPreviewWebView: () => ({
    mode: "rnc",
    Component: jest.requireActual("react-native").View,
  }),
  STATIC_HTML_ORIGIN_WHITELIST: ["about:blank"],
  useStaticOnlyNavigation: () => () => true,
}));
jest.mock("@/hooks/useDeferredWebViewMount", () => ({
  useDeferredWebViewMount: () => ({ canMount: true, onLoaded: jest.fn() }),
}));
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe("MathFormulaWebView layout", () => {
  it.each([
    String.raw`\int_0^1 x^2\,dx=\frac{1}{3}`,
    String.raw`\lim_{x\to0}\frac{\sin x}{x}=1`,
    String.raw`\begin{pmatrix}1&2\\3&4\end{pmatrix}`,
  ])("reserves space before the first content measurement for %s", async (latex) => {
    const { getByTestId } = await render(
      <MathFormulaWebView latex={latex} displayMode minHeight={48} />,
    );
    // minHeight is a floor; it must not replace the tall-math first-paint estimate.
    expect(getByTestId("math-formula-webview")).toHaveStyle({ height: 84 });
  });

  it("applies even a small height increase that could contain a lower limit", async () => {
    const { getByTestId } = await render(
      <MathFormulaWebView latex={String.raw`\frac{1}{3}`} displayMode minHeight={48} />,
    );
    const webview = getByTestId("math-formula-webview");
    await fireEvent(webview, "message", { nativeEvent: { data: JSON.stringify({ h: 86 }) } });
    expect(webview).toHaveStyle({ height: 86 });
    await fireEvent(webview, "message", { nativeEvent: { data: JSON.stringify({ h: 74 }) } });
    expect(webview).toHaveStyle({ height: 86 });
  });
});
