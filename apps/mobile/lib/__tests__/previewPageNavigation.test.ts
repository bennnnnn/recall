import { allowPreviewPageNavigation, PREVIEW_PAGE_ORIGIN_WHITELIST } from "@/lib/webView";

jest.mock("react-native", () => ({
  NativeModules: {},
  TurboModuleRegistry: { get: () => null },
}));

const PAGE = "file:///var/mobile/Containers/Data/Application/A1/Library/Caches/preview-pages/mermaid-3b2f6a9c41d0e1f2.html";

describe("preview page navigation", () => {
  it("lets every URL reach the guard so nothing is handed to the OS", () => {
    // A URL that misses originWhitelist goes to Linking.openURL; "*" means
    // the guard decides, and a refusal opens nothing.
    expect(PREVIEW_PAGE_ORIGIN_WHITELIST).toEqual(["*"]);
  });

  it.each([
    ["the page itself", PAGE],
    ["the page as iOS reports it", PAGE.replace("file:///var/", "file:///private/var/")],
    ["the page with a fragment", `${PAGE}#diagram`],
    ["a blank document", "about:blank"],
  ])("loads %s", (_name, url) => {
    expect(allowPreviewPageNavigation(PAGE, { url })).toBe(true);
    expect(allowPreviewPageNavigation(PAGE, { nativeEvent: { url } })).toBe(true);
  });

  it.each([
    // A link in a chart (Vega href), a diagram or page script.
    ["a web page", "https://example.com/track?memory=1"],
    ["plain http", "http://localhost/"],
    ["another cached file", "file:///var/mobile/Containers/Data/Application/A1/Library/Caches/att-1-2-doc.pdf"],
    ["another preview page", PAGE.replace("mermaid-3b2f6a9c41d0e1f2", "chart-0123456789abcdef")],
    ["app data", "file:///data/user/0/com.recall.app/files/session.json"],
    ["a data document", "data:text/html,<script>alert(1)</script>"],
    ["an app link", "recall://chat/1"],
    ["a script URL", "javascript:alert(1)"],
    ["nothing", ""],
  ])("refuses %s", (_name, url) => {
    expect(allowPreviewPageNavigation(PAGE, { url })).toBe(false);
  });
});
