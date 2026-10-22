import {
  allowPreviewPageNavigation,
  PREVIEW_PAGE_ORIGIN_WHITELIST,
  previewPageLinkToOpen,
} from "@/lib/webView";

const mockPlatform = { OS: "ios" };
jest.mock("react-native", () => ({
  NativeModules: {},
  TurboModuleRegistry: { get: () => null },
  Linking: { openURL: jest.fn() },
  get Platform() {
    return mockPlatform;
  },
}));

const CACHES = "file:///var/mobile/Containers/Data/Application/A1/Library/Caches";
const PAGE = `${CACHES}/preview-pages/mermaid-3b2f6a9c41d0e1f2.html`;

describe("preview page navigation", () => {
  it("lets every URL reach the guard so nothing is handed to the OS", () => {
    // A URL that misses originWhitelist goes to Linking.openURL; "*" means
    // the guard below decides, and a refusal opens nothing.
    expect(PREVIEW_PAGE_ORIGIN_WHITELIST).toEqual(["*"]);
  });

  it.each([
    ["the page itself", PAGE],
    ["the page as iOS reports it", PAGE.replace("file:///var/", "file:///private/var/")],
    ["the page with a fragment", `${PAGE}#diagram`],
    ["the page spelled with escapes", PAGE.replace("preview-pages", "preview%2Dpages")],
  ])("loads %s", (_name, url) => {
    expect(allowPreviewPageNavigation(PAGE, { url })).toBe(true);
    expect(allowPreviewPageNavigation(PAGE, { nativeEvent: { url } })).toBe(true);
  });

  it("lets a subframe go blank, never the card itself", () => {
    expect(allowPreviewPageNavigation(PAGE, { url: "about:blank", isTopFrame: false })).toBe(true);
    expect(allowPreviewPageNavigation(PAGE, { url: "about:blank", isTopFrame: true })).toBe(false);
    expect(allowPreviewPageNavigation(PAGE, { url: "about:blank" })).toBe(false);
  });

  it.each([
    // A link in a chart (Vega href), a diagram or page script.
    ["a web page", "https://example.com/track?memory=1"],
    ["plain http", "http://localhost/"],
    ["another cached file", `${CACHES}/att-1-2-doc.pdf`],
    ["another preview page", PAGE.replace("mermaid-3b2f6a9c41d0e1f2", "chart-0123456789abcdef")],
    ["a page of that name elsewhere", PAGE.replace("/A1/", "/B2/")],
    ["app data", "file:///data/user/0/com.recall.app/files/session.json"],
    ["a data document", "data:text/html,<script>alert(1)</script>"],
    ["an app link", "recall://chat/1"],
    ["a script URL", "javascript:alert(1)"],
    ["nothing", ""],
  ])("refuses %s", (_name, url) => {
    expect(allowPreviewPageNavigation(PAGE, { url })).toBe(false);
  });
});

describe("previewPageLinkToOpen", () => {
  beforeEach(() => {
    mockPlatform.OS = "ios";
  });

  it("opens a link the user tapped on iOS, as a chat link would", () => {
    expect(previewPageLinkToOpen({ url: "https://example.com/a", navigationType: "click", isTopFrame: true })).toBe(
      "https://example.com/a",
    );
    expect(previewPageLinkToOpen({ nativeEvent: { url: "mailto:a@b.test", navigationType: "click" } })).toBe(
      "mailto:a@b.test",
    );
  });

  it("opens nothing on iOS that a tap did not start", () => {
    expect(previewPageLinkToOpen({ url: "https://example.com", navigationType: "other" })).toBeNull();
    expect(previewPageLinkToOpen({ url: "https://example.com" })).toBeNull();
  });

  it("opens a refused top-frame link on Android, which does not say what started it", () => {
    mockPlatform.OS = "android";
    expect(previewPageLinkToOpen({ url: "https://example.com/b" })).toBe("https://example.com/b");
  });

  it("opens nothing for a subframe", () => {
    expect(
      previewPageLinkToOpen({ url: "https://example.com", navigationType: "click", isTopFrame: false }),
    ).toBeNull();
  });

  it.each([
    ["a cached file", `${CACHES}/att-1-2-doc.pdf`],
    ["app data", "file:///data/user/0/com.recall.app/files/session.json"],
    ["an app link", "recall://chat/1"],
    ["a data document", "data:text/html,hi"],
    ["a script URL", "javascript:alert(1)"],
    ["a relative path", "secrets.json"],
  ])("never opens %s", (_name, url) => {
    expect(previewPageLinkToOpen({ url, navigationType: "click" })).toBeNull();
    mockPlatform.OS = "android";
    expect(previewPageLinkToOpen({ url })).toBeNull();
  });
});
