import { render } from "@testing-library/react-native";

import { MathBlock, MathInline } from "@/components/rich/MathView";

// Same guard pattern as MermaidBlock.test.tsx: force both WebView backends
// unavailable so MathBlock takes its no-WebView (MathText) rendering path,
// matching a real device without either native module linked (Expo Go).
jest.mock("react-native-webview", () => {
  throw new Error("react-native-webview native module is not linked (test)");
});
jest.mock("@expo/dom-webview", () => {
  throw new Error("@expo/dom-webview native module is not linked (test)");
});

describe("MathInline", () => {
  it("renders trimmed latex as inline MathText", async () => {
    const { getByText } = await render(<MathInline latex="  x + 1  " />);
    expect(getByText("x + 1")).toBeOnTheScreen();
  });
});

describe("MathBlock", () => {
  it("renders a single equation as one block via the MathText fallback path", async () => {
    const { getByText } = await render(<MathBlock latex="x + 1 = 2" />);
    expect(getByText("x + 1 = 2")).toBeOnTheScreen();
  });

  it("renders nothing for an empty/redundant-dollar-wrapped-to-empty body", async () => {
    const { toJSON } = await render(<MathBlock latex="   " />);
    expect(toJSON()).toBeNull();
  });

  it("splits a multi-line fence body into one MathBlock per line", async () => {
    const { getByText } = await render(<MathBlock latex={"x = 1\ny = 2"} />);
    expect(getByText("x = 1")).toBeOnTheScreen();
    expect(getByText("y = 2")).toBeOnTheScreen();
  });
});
