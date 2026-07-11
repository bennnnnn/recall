// Proof-of-pattern component test for the WebView-gated preview components:
// when the native preview WebView isn't linked, MermaidBlock must render its
// documented static-source fallback instead of crashing. See lib/webView.ts
// (getPreviewWebView) for the detection/fallback chain this exercises.
//
// react-native-webview and @expo/dom-webview are the two require() calls
// getPreviewWebView() falls through in turn; forcing both to throw is how a
// real device without either native module linked (e.g. Expo Go) behaves
// from getPreviewWebView()'s point of view, so this keeps the guard's own
// fallback logic under real test rather than stubbing lib/webView.ts itself.
jest.mock("react-native-webview", () => {
  throw new Error("react-native-webview native module is not linked (test)");
});
jest.mock("@expo/dom-webview", () => {
  throw new Error("@expo/dom-webview native module is not linked (test)");
});

// expo-clipboard / expo-web-browser wrap native modules that this test's
// plain @react-native/jest-preset environment (no jest-expo) doesn't stub.
// MermaidBlock only calls them from button-press handlers, not during
// render, so simple no-op fakes are enough to keep import-time safe.
jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn(),
}));
jest.mock("expo-web-browser", () => ({
  openBrowserAsync: jest.fn(),
}));

// Icon glyphs aren't relevant to this test and pulling in the real font
// asset registration is unnecessary risk for a fallback-rendering check.
jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

import { render } from "@testing-library/react-native";

import { MermaidBlock } from "@/components/rich/MermaidBlock";

describe("MermaidBlock", () => {
  it("renders the static source fallback when no preview WebView is available", async () => {
    const content = "graph TD; A-->B;";

    // RTL v14 made render() async (it now drives an async act() internally).
    const { getByText } = await render(<MermaidBlock content={content} />);

    expect(getByText(content)).toBeOnTheScreen();
    expect(
      getByText("Build the app to preview diagrams inline."),
    ).toBeOnTheScreen();
  });
});
