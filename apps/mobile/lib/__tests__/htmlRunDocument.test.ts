import { prepareHtmlRunDocument } from "@/lib/htmlRunDocument";

const PAGE = `<!DOCTYPE html><html><head><script>window.user = 1</script></head>
<body><h1 title="a &amp; b">Hi "there"</h1></body></html>`;

/** The page frame's srcdoc, decoded the way an HTML parser decodes the attribute. */
function pageFrame(doc: string): { sandbox: string[]; page: string } {
  // A raw `"` inside the value would end this match early, so a page that
  // could close the attribute fails the round trip below.
  const frame = /<iframe sandbox="([^"]*)" srcdoc="([^"]*)"><\/iframe>/.exec(doc);
  if (!frame) throw new Error("no sandboxed page frame");
  const page = frame[2].replace(/&quot;/g, '"').replace(/&amp;/g, "&");
  return { sandbox: frame[1].split(/\s+/).filter(Boolean), page };
}

describe("prepareHtmlRunDocument", () => {
  it("runs the page in a frame that cannot navigate the preview or open windows", () => {
    const doc = prepareHtmlRunDocument(PAGE);
    const { sandbox } = pageFrame(doc);
    expect(sandbox).toContain("allow-scripts");
    for (const token of [
      "allow-top-navigation",
      "allow-top-navigation-by-user-activation",
      "allow-top-navigation-to-custom-protocols",
      "allow-popups",
      "allow-popups-to-escape-sandbox",
      "allow-same-origin",
      "allow-forms",
    ]) {
      expect(sandbox).not.toContain(token);
    }
    expect(doc.match(/<iframe\b/g)).toHaveLength(1);
  });

  it("keeps the page whole inside srcdoc, so it cannot close the attribute", () => {
    const hostile = `<p>"></iframe><script>top.location = "https://cdn.jsdelivr.net/x.html"</script>&quot;</p>`;
    const doc = prepareHtmlRunDocument(hostile);
    const { page } = pageFrame(doc);
    expect(page).toContain(hostile);
    // Nothing of the page reaches the wrapper's own markup.
    expect(doc.replace(/srcdoc="[^"]*"/, "")).not.toContain("top.location");
  });

  it("carries none of the location / window.open overrides that never worked", () => {
    // window.location is [LegacyUnforgeable]: redefining href or replacing
    // assign/replace fails silently, so these only looked like protection.
    const doc = prepareHtmlRunDocument(PAGE);
    const page = doc.includes("srcdoc=") ? pageFrame(doc).page : "";
    for (const text of [doc, page]) {
      expect(text).not.toMatch(/defineProperty\(\s*loc/);
      expect(text).not.toMatch(/\.assign\s*=/);
      expect(text).not.toMatch(/\.replace\s*=\s*function/);
      expect(text).not.toMatch(/window\.open\s*=/);
    }
  });

  it("puts the live CSP and the link trap ahead of every page script", () => {
    const { page } = pageFrame(prepareHtmlRunDocument(PAGE));
    const cspAt = page.indexOf('http-equiv="Content-Security-Policy"');
    const trapAt = page.indexOf('addEventListener("click"');
    const userAt = page.indexOf("window.user = 1");
    expect(cspAt).toBeGreaterThan(-1);
    expect(page).toContain("https://cdn.jsdelivr.net");
    expect(trapAt).toBeGreaterThan(cspAt);
    expect(userAt).toBeGreaterThan(trapAt);
    expect(page).toContain('<h1 title="a &amp; b">Hi "there"</h1>');
  });

  it("strips meta refresh from the page", () => {
    const { page } = pageFrame(
      prepareHtmlRunDocument(
        '<html><head><meta http-equiv="refresh" content="0;url=https://evil.example/x"></head><body>ok</body></html>',
      ),
    );
    expect(page.toLowerCase()).not.toContain("refresh");
    expect(page).not.toContain("evil.example");
  });

  it("reports an empty page through the wrapper, which alone can reach the app", () => {
    const doc = prepareHtmlRunDocument(PAGE);
    const { page } = pageFrame(doc);
    // iOS gives only the main frame window.ReactNativeWebView.
    expect(page).toContain("parent.postMessage(");
    expect(page).not.toContain("ReactNativeWebView");
    const wrapper = doc.replace(/srcdoc="[^"]*"/, "");
    expect(wrapper).toContain("event.source !== frame.contentWindow");
    expect(wrapper).toContain("ReactNativeWebView.postMessage(");
  });
});
