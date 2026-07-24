import {
  createHtmlRunNavigationGuard,
  createStaticOnlyNavigationGuard,
  isExternalHttpUrl,
  isPreviewFrameworkUrl,
  isPreviewInlineDocumentUrl,
  PREVIEW_INLINE_BASE_URL,
} from "@/lib/staticOnlyNavigationGuard";

describe("isPreviewFrameworkUrl", () => {
  it("allows blank / data / file / applewebdata loads", () => {
    expect(isPreviewFrameworkUrl("")).toBe(true);
    expect(isPreviewFrameworkUrl("about:blank")).toBe(true);
    expect(isPreviewFrameworkUrl("about:srcdoc")).toBe(true);
    expect(isPreviewFrameworkUrl("data:text/html,hi")).toBe(true);
    expect(isPreviewFrameworkUrl("file:///tmp/preview.html")).toBe(true);
    expect(isPreviewFrameworkUrl("applewebdata://uuid/doc")).toBe(true);
  });

  it("does not treat https as framework", () => {
    expect(isPreviewFrameworkUrl("https://localhost/")).toBe(false);
    expect(isPreviewFrameworkUrl("https://evil.example")).toBe(false);
  });
});

describe("isPreviewInlineDocumentUrl", () => {
  it("allows the RNC inline HTML baseUrl only on localhost", () => {
    expect(isPreviewInlineDocumentUrl(PREVIEW_INLINE_BASE_URL)).toBe(true);
    expect(isPreviewInlineDocumentUrl("https://localhost")).toBe(true);
    expect(isPreviewInlineDocumentUrl("http://127.0.0.1/")).toBe(true);
    expect(isPreviewInlineDocumentUrl("https://evil.example/")).toBe(false);
    expect(isPreviewInlineDocumentUrl("about:blank")).toBe(false);
  });
});

describe("isExternalHttpUrl", () => {
  it("detects http(s)", () => {
    expect(isExternalHttpUrl("https://example.com")).toBe(true);
    expect(isExternalHttpUrl("http://example.com")).toBe(true);
    expect(isExternalHttpUrl("about:blank")).toBe(false);
  });
});

describe("createStaticOnlyNavigationGuard", () => {
  it("allows repeated about:blank / data loads (WKWebView bootstrap)", () => {
    const guard = createStaticOnlyNavigationGuard();
    expect(guard.shouldAllow("about:blank")).toBe(true);
    expect(guard.shouldAllow("about:blank")).toBe(true);
    expect(guard.shouldAllow("data:text/html,%3Ch1%3Ehi%3C%2Fh1%3E")).toBe(true);
  });

  it("allows the inline document baseUrl (otherwise Run tab is blank)", () => {
    const guard = createStaticOnlyNavigationGuard();
    expect(guard.shouldAllow(PREVIEW_INLINE_BASE_URL)).toBe(true);
    expect(guard.shouldAllow("https://localhost/")).toBe(true);
    expect(guard.shouldAllow("https://localhost/?v=1")).toBe(true);
  });

  it("denies open-web http(s) navigations (phishing)", () => {
    const guard = createStaticOnlyNavigationGuard();
    guard.shouldAllow("about:blank");
    expect(guard.shouldAllow("https://evil.example/phish")).toBe(false);
    expect(guard.shouldAllow("http://evil.example/")).toBe(false);
  });

  it("allows one unknown-scheme load, then denies further unknowns", () => {
    const guard = createStaticOnlyNavigationGuard();
    expect(guard.shouldAllow("blob:opaque-1")).toBe(true);
    expect(guard.shouldAllow("blob:opaque-2")).toBe(false);
  });

  it("re-arms the unknown one-shot after reset", () => {
    const guard = createStaticOnlyNavigationGuard();
    guard.shouldAllow("blob:a");
    expect(guard.shouldAllow("blob:b")).toBe(false);
    guard.reset();
    expect(guard.shouldAllow("blob:c")).toBe(true);
  });

  it("gives each guard instance independent state", () => {
    const guardA = createStaticOnlyNavigationGuard();
    const guardB = createStaticOnlyNavigationGuard();
    expect(guardA.shouldAllow("blob:a")).toBe(true);
    expect(guardA.shouldAllow("blob:b")).toBe(false);
    expect(guardB.shouldAllow("blob:a")).toBe(true);
  });
});

describe("createHtmlRunNavigationGuard", () => {
  it("allows CDN subresource http(s) but blocks top-level open-web nav", () => {
    const guard = createHtmlRunNavigationGuard();
    expect(guard.shouldAllow("https://cdn.example/app.js", false)).toBe(true);
    expect(guard.shouldAllow("https://evil.example/phish", true)).toBe(false);
    expect(guard.shouldAllow(PREVIEW_INLINE_BASE_URL, true)).toBe(true);
    expect(guard.shouldAllow("about:blank", true)).toBe(true);
  });
});
