import {
  createStaticOnlyNavigationGuard,
  isExternalHttpUrl,
  isPreviewFrameworkUrl,
  isPreviewInlineDocumentUrl,
} from "@/lib/staticOnlyNavigationGuard";

import { INLINE_DOCUMENT_URL, LOOPBACK_URLS } from "./fixtures/loopbackUrls";

type DevFlag = { __DEV__?: boolean };

/** Runs the same checks in a release build and a development one. */
const BUILDS = [
  { build: "release", dev: false },
  { build: "development", dev: true },
];

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

describe.each(BUILDS)("in a $build build", ({ dev }) => {
  // Nothing in development loads a preview from localhost (the dev-only
  // @expo/dom-webview never asks these guards; vendored libraries are read
  // from Metro natively, then inlined), so a dev build accepts no more.
  beforeEach(() => {
    (globalThis as DevFlag).__DEV__ = dev;
  });
  afterEach(() => {
    delete (globalThis as DevFlag).__DEV__;
  });

  describe("isPreviewInlineDocumentUrl", () => {
    it("accepts the URL react-native-webview gives inline HTML", () => {
      expect(isPreviewInlineDocumentUrl(INLINE_DOCUMENT_URL)).toBe(true);
    });

    it.each(LOOPBACK_URLS)("refuses %s: a server on the phone is not the inline document", (url) => {
      expect(isPreviewInlineDocumentUrl(url)).toBe(false);
    });

    it.each(["https://evil.example/", "about:srcdoc", ""])("refuses %j", (url) => {
      expect(isPreviewInlineDocumentUrl(url)).toBe(false);
    });
  });

  describe("createStaticOnlyNavigationGuard", () => {
    it("loads the inline document (otherwise the preview is blank)", () => {
      const guard = createStaticOnlyNavigationGuard();
      expect(guard.shouldAllow(INLINE_DOCUMENT_URL)).toBe(true);
      expect(guard.shouldAllow({ url: INLINE_DOCUMENT_URL, isTopFrame: true })).toBe(true);
    });

    it.each(LOOPBACK_URLS)("never navigates to %s", (url) => {
      const guard = createStaticOnlyNavigationGuard();
      guard.shouldAllow(INLINE_DOCUMENT_URL);
      expect(guard.shouldAllow({ url, isTopFrame: true })).toBe(false);
      expect(guard.shouldAllow({ url, isTopFrame: false })).toBe(false);
    });
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
