/** Modes from `getPreviewWebView()` that can host inline HTML math. */
export type InlineMathWebViewMode = "rnc" | "expo-dom";

/**
 * True when KaTeX/MathJax may mount with `source={{ html }}`.
 *
 * Both `react-native-webview` (dev client) and `@expo/dom-webview` (Expo Go)
 * can render inline HTML math. Charts, Mermaid, chemistry, and the HTML Run
 * tab stay RNC-only — expo-dom has known blanks on those file:// / heavier
 * paths (`HtmlPreviewModal`).
 */
export function supportsInlineHtmlMathWebView(
  mode: InlineMathWebViewMode | null | undefined,
): boolean {
  return mode === "rnc" || mode === "expo-dom";
}
