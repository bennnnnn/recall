import { render } from "@testing-library/react-native";

import { HtmlPreviewModal } from "@/components/HtmlPreviewModal";

// The Run tab executes model-written JavaScript. A reply that sets
// `location` or calls `window.open` must stay inside the sandbox: with no
// guard, react-native-webview opened any URL outside originWhitelist through
// Linking.openURL (Safari, the dialer, a deep link into the app).
const mockWebViewProps: Record<string, unknown>[] = [];

jest.mock("@/lib/webView", () => {
  const actual = jest.requireActual("@/lib/webView");
  const { View } = jest.requireActual("react-native");
  const FakeWebView = (props: Record<string, unknown>) => {
    mockWebViewProps.push(props);
    return <View testID="run-webview" />;
  };
  return {
    ...actual,
    getPreviewWebView: () => ({ Component: FakeWebView, mode: "rnc" }),
  };
});
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(),
  EncodingType: { UTF8: "utf8" },
}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));

const HOSTILE_HTML = `<!DOCTYPE html><html><head></head><body>
<script>location = "https://accounts-google.example/signin";</script>
</body></html>`;

describe("HtmlPreviewModal Run tab navigation", () => {
  it("decides every navigation itself and refuses to leave the preview", async () => {
    mockWebViewProps.length = 0;
    const { getByTestId } = await render(
      <HtmlPreviewModal visible html={HOSTILE_HTML} onClose={() => {}} />,
    );
    expect(getByTestId("run-webview")).toBeOnTheScreen();

    const props = mockWebViewProps[mockWebViewProps.length - 1];
    expect(props.originWhitelist).toEqual(["*"]);
    const decide = props.onShouldStartLoadWithRequest as (request: unknown) => boolean;
    expect(typeof decide).toBe("function");
    expect(decide({ url: "about:blank", isTopFrame: true })).toBe(true);
    expect(decide({ url: "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js" })).toBe(true);
    expect(decide({ url: "https://accounts-google.example/signin", isTopFrame: true })).toBe(
      false,
    );
    expect(decide({ url: "tel:+19005550100", isTopFrame: true })).toBe(false);
    expect(decide({ url: "recall://settings", isTopFrame: true })).toBe(false);
  });
});
