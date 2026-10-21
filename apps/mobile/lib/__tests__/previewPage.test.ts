import { previewPageConfigScript, previewPageStartScript } from "@/lib/previewPage";

import { previewPageSandbox } from "./fixtures/previewPageSandbox";

/** A page whose start function records each config it starts with. */
function recordingPage() {
  const received: unknown[] = [];
  const page = previewPageSandbox({ received });
  const html = `<script>${previewPageStartScript("function (config) { received.push(config); }")}</script>`;
  return { page, html, received };
}

describe("preview page handshake", () => {
  it("starts with the data handed in before the page script ran", () => {
    // iOS: injectedJavaScriptBeforeContentLoaded runs at document start.
    const { page, html, received } = recordingPage();
    page.hand({ source: "graph TD; A-->B" });
    expect(received).toEqual([]);
    page.loadPage(html);
    expect(received).toEqual([{ source: "graph TD; A-->B" }]);
  });

  it("starts when the data arrives after the page script ran", () => {
    // Android may run the first injection late; injectedJavaScript always follows the load.
    const { page, html, received } = recordingPage();
    page.loadPage(html);
    expect(received).toEqual([]);
    page.hand({ source: "graph LR; X-->Y" });
    expect(received).toEqual([{ source: "graph LR; X-->Y" }]);
  });

  it("starts once, however many times the data arrives", () => {
    const { page, html, received } = recordingPage();
    page.hand({ n: 1 });
    page.loadPage(html);
    page.hand({ n: 1 });
    page.hand({ n: 1 });
    expect(received).toEqual([{ n: 1 }]);
  });

  it.each([
    ["a closing script tag", "</script><script>alert(1)</script>"],
    ["a backtick and a template placeholder", "C`${alert(1)}`C"],
    ["quotes and backslashes", `"'\\"\\n`],
    ["line and paragraph separators", "a\u2028b\u2029c"],
    ["a comment opener", "<!--<script>"],
  ])("hands %s to the page unchanged", (_name, value) => {
    const page = previewPageSandbox();
    page.hand({ value, nested: { list: [value] } });
    expect(page.window.RECALL_PREVIEW).toEqual({ value, nested: { list: [value] } });
  });

  it("keeps the separators escaped in the script text", () => {
    const script = previewPageConfigScript({ value: "a\u2028b\u2029c" });
    expect(script).not.toMatch(/[\u2028\u2029]/);
    expect(script).toContain("a\\u2028b\\u2029c");
  });

  it("ends the injected script with a value the WebView can return", () => {
    expect(previewPageConfigScript({}).endsWith("true;")).toBe(true);
  });
});
