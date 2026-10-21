import {
  buildMermaidPageHtml,
  MERMAID_PAGE,
  mermaidPreviewConfig,
} from "@/lib/mermaidPreviewHtml";
import { PREVIEW_CSP } from "@/lib/previewSandbox";

import { previewPageSandbox, settle } from "./fixtures/previewPageSandbox";

const LIGHT = { bg: "#FFFFFF", danger: "#D92D20", isDark: false };
const DARK = { bg: "#101010", danger: "#F97066", isDark: true };
const LIBRARY = "/*mermaid*/";

function fakeMermaid(run: () => Promise<void>) {
  return { initialize: jest.fn(), run: jest.fn(run) };
}

describe("buildMermaidPageHtml", () => {
  it("is one page for every diagram: the sandbox CSP, the library once, no diagram", () => {
    const html = MERMAID_PAGE.build({ mermaid: LIBRARY });
    expect(MERMAID_PAGE.libraries).toEqual(["mermaid"]);
    expect(html).toBe(buildMermaidPageHtml(LIBRARY));
    expect(html).toContain(`content="${PREVIEW_CSP}"`);
    expect(html).toContain("connect-src 'none'");
    expect(html.split(LIBRARY)).toHaveLength(2);
    expect(html).not.toContain(LIGHT.bg);
  });

  it("keeps a closing script tag in the library from ending its script", () => {
    expect(buildMermaidPageHtml("var a = '</script>';")).toContain("var a = '<\\/script>';");
  });

  it("draws the diagram it is handed, in strict mode and the block's theme", async () => {
    const mermaid = fakeMermaid(() => Promise.resolve());
    const page = previewPageSandbox({ mermaid });
    page.loadPage(buildMermaidPageHtml(LIBRARY));
    expect(mermaid.run).not.toHaveBeenCalled();

    page.hand(mermaidPreviewConfig("  graph TD; A-->B  ", DARK));
    expect(page.elements.diagram.textContent).toBe("graph TD; A-->B");
    expect(page.css).toEqual({ "--bg": DARK.bg, "--danger": DARK.danger });
    expect(mermaid.initialize).toHaveBeenCalledWith(
      expect.objectContaining({ startOnLoad: false, securityLevel: "strict", theme: "dark" }),
    );
    expect(mermaid.run).toHaveBeenCalledWith({ nodes: [page.elements.diagram] });

    await settle();
    page.runFrames();
    expect(page.posted).toEqual([{ kind: "mermaid-size", height: 116 }]);
  });

  it("reports a diagram Mermaid cannot read", async () => {
    const page = previewPageSandbox({ mermaid: fakeMermaid(() => Promise.reject(new Error("Parse error"))) });
    page.loadPage(buildMermaidPageHtml(LIBRARY));
    page.hand(mermaidPreviewConfig("graph TD; A-->", LIGHT));
    await settle();
    expect(page.posted).toEqual([{ kind: "mermaid-error", message: "Parse error" }]);
    expect(page.elements.err.textContent).toBe("Diagram error: Parse error");
  });
});

describe("mermaidPreviewConfig", () => {
  it("names Mermaid's theme for the app's", () => {
    expect(mermaidPreviewConfig("graph TD; A-->B", LIGHT)).toEqual({
      source: "graph TD; A-->B",
      theme: "neutral",
      colors: { bg: LIGHT.bg, danger: LIGHT.danger },
    });
    expect(mermaidPreviewConfig("graph TD; A-->B", DARK).theme).toBe("dark");
  });
});
