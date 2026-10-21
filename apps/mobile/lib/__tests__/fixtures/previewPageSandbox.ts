/**
 * Runs a preview page's own script and a block's config script against fake
 * browser globals, so a test sees what the page does with the data a WebView
 * hands it (lib/previewPage.ts) without a browser.
 */
import { previewPageConfigScript, type PreviewPageConfig } from "@/lib/previewPage";

type FakeElement = { textContent: string; style: Record<string, string> };

export function previewPageSandbox(globals: Record<string, unknown> = {}) {
  const posted: unknown[] = [];
  const css: Record<string, string> = {};
  const elements: Record<string, FakeElement> = {};
  const frames: (() => void)[] = [];
  const window: Record<string, unknown> = {
    ReactNativeWebView: { postMessage: (data: string) => posted.push(JSON.parse(data)) },
  };
  const document = {
    documentElement: {
      style: {
        setProperty: (name: string, value: string) => {
          css[name] = value;
        },
      },
    },
    getElementById: (id: string) => (elements[id] ??= { textContent: "", style: {} }),
    querySelector: () => null,
    body: { scrollHeight: 100 },
  };
  const scope: Record<string, unknown> = {
    window,
    document,
    requestAnimationFrame: (frame: () => void) => frames.push(frame),
    ...globals,
  };
  const run = (source: string) => new Function(...Object.keys(scope), source)(...Object.values(scope));

  return {
    window,
    /** What the page posted to the app, parsed. */
    posted,
    /** CSS variables the page set on its root. */
    css,
    elements,
    /** The page's own script: its last inline <script>, after the libraries. */
    loadPage(html: string) {
      const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
      run(scripts[scripts.length - 1]?.[1] ?? "");
    },
    /** What the WebView injects for one block. */
    hand(config: PreviewPageConfig) {
      run(previewPageConfigScript(config));
    },
    runFrames() {
      frames.splice(0).forEach((frame) => frame());
    },
  };
}

/** Lets the page's promise callbacks run. */
export function settle(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}
