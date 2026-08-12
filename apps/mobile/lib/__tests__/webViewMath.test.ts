import { supportsInlineHtmlMathWebView } from "@/lib/mathWebViewSupport";

describe("supportsInlineHtmlMathWebView", () => {
  it("allows RNC (dev client) and expo-dom (Expo Go)", () => {
    expect(supportsInlineHtmlMathWebView("rnc")).toBe(true);
    expect(supportsInlineHtmlMathWebView("expo-dom")).toBe(true);
  });

  it("rejects missing preview (true static fallback)", () => {
    expect(supportsInlineHtmlMathWebView(null)).toBe(false);
    expect(supportsInlineHtmlMathWebView(undefined)).toBe(false);
  });
});
