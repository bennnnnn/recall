import { PREVIEW_CSP, injectPreviewCsp } from "@/lib/previewSandbox";

describe("PREVIEW_CSP", () => {
  it("blocks network egress and forms, allows inline scripts", () => {
    expect(PREVIEW_CSP).toContain("default-src 'none'");
    expect(PREVIEW_CSP).toContain("script-src 'unsafe-inline' https:");
    expect(PREVIEW_CSP).toContain("connect-src 'none'");
    expect(PREVIEW_CSP).toContain("form-action 'none'");
    expect(PREVIEW_CSP).toContain("base-uri 'none'");
    expect(PREVIEW_CSP).toContain("sandbox allow-scripts");
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
});
