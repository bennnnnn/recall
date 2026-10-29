import { allowHtmlRunNavigation, HTML_RUN_ORIGIN_WHITELIST } from "@/lib/webView";

jest.mock("react-native", () => ({
  NativeModules: {},
  TurboModuleRegistry: { get: () => null },
}));

describe("HTML Run navigation", () => {
  it("lets every URL reach the guard so nothing is handed to the OS", () => {
    // A URL that misses originWhitelist goes to Linking.openURL; "*" means
    // the guard below decides, and a refusal opens nothing.
    expect(HTML_RUN_ORIGIN_WHITELIST).toEqual(["*"]);
  });

  it.each([
    "about:blank",
    "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
    "https://unpkg.com/three@0.160.0/build/three.module.js",
    "https://fonts.googleapis.com/css2?family=Inter",
  ])("keeps loading %s in the preview", (url) => {
    expect(allowHtmlRunNavigation({ url })).toBe(true);
    expect(allowHtmlRunNavigation({ nativeEvent: { url } })).toBe(true);
  });

  it.each([
    // Page script: location = "…" / window.open(…) / a link it clicks.
    "https://accounts-google.example/signin",
    "http://cdn.jsdelivr.net/npm/x.js",
    "https://cdn.jsdelivr.net.evil.example/phish.html",
    // A server on the phone itself: the inline document is about:blank.
    "https://localhost/",
    "http://127.0.0.1:8081/index.bundle",
    "tel:+19005550100",
    "sms:+15550100?body=hi",
    "mailto:someone@example.com",
    "recall://settings/data-controls",
    "intent://scan/#Intent;scheme=zxing;end",
    "file:///etc/hosts",
    "data:text/html,<h1>hi</h1>",
    "",
  ])("refuses %s without opening it anywhere", (url) => {
    expect(allowHtmlRunNavigation({ url })).toBe(false);
  });
});
