import { render } from "@testing-library/react-native";

import { MathFormulaWebView } from "@/components/rich/MathFormulaWebView";

// Same guard pattern as MermaidBlock.test.tsx — without either WebView
// backend linked, MathFormulaWebView must fall back to the static
// engine-badge + raw-latex + "use a dev build" hint, never crash.
jest.mock("react-native-webview", () => {
  throw new Error("react-native-webview native module is not linked (test)");
});
jest.mock("@expo/dom-webview", () => {
  throw new Error("@expo/dom-webview native module is not linked (test)");
});

describe("MathFormulaWebView", () => {
  it("renders the KaTeX-badged static fallback when no preview WebView is available", async () => {
    const { getByText } = await render(<MathFormulaWebView latex="x^2 + 1" displayMode />);

    expect(getByText("x^2 + 1")).toBeOnTheScreen();
    expect(getByText("KaTeX preview")).toBeOnTheScreen();
    expect(getByText("Use a dev build for rendered math.")).toBeOnTheScreen();
  });

  it("badges the fallback as MathJax for the environments KaTeX 0.17 can't render", async () => {
    // multline/eqnarray are the two environments confirmed unsupported by
    // the bundled KaTeX version (see mathHtml.ts's HEAVY_MATH_RE) — those
    // route to the MathJax engine even in the no-WebView fallback badge.
    const { getByText } = await render(
      <MathFormulaWebView latex={"\\begin{multline}x = 1\\end{multline}"} displayMode />,
    );

    expect(getByText("MathJax preview")).toBeOnTheScreen();
  });

  it("omits the badge and hint in compact mode", async () => {
    const { queryByText, getByText } = await render(
      <MathFormulaWebView latex="x^2" compact />,
    );

    expect(getByText("x^2")).toBeOnTheScreen();
    expect(queryByText("KaTeX preview")).toBeNull();
    expect(queryByText("Use a dev build for rendered math.")).toBeNull();
  });
});
