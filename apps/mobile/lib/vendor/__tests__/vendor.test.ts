// Integrity checks for the vendored web libraries. They ship as app assets
// (assets/vendor, read by lib/vendorAssets.ts), not as TypeScript strings in the JS
// bundle (code-health audit DEAD-03). These lock in what the generator
// (scripts/vendor-cdn.mjs) guarantees, so an empty file, a re-introduced CDN URL or
// a hand edit is caught here rather than as a blank WebView offline.

// The lib test project has Jest types but no Node type package.
declare const __dirname: string;
const { createHash } = jest.requireActual<{
  createHash(name: string): { update(value: string): { digest(encoding: string): string } };
}>("node:crypto");
const { readFileSync, readdirSync } = jest.requireActual<{
  readFileSync(path: string, encoding: "utf8"): string;
  readdirSync(path: string): string[];
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

const ASSETS = join(__dirname, "../../../assets/vendor");
const manifest = JSON.parse(readFileSync(join(__dirname, "../manifest.json"), "utf8")) as {
  sha256: Record<string, string>;
};
const read = (file: string): string => readFileSync(join(ASSETS, file), "utf8");
const sha = (value: string): string => createHash("sha256").update(value).digest("hex").slice(0, 16);

// Manifest key → asset file.
const FILES: Record<string, string> = {
  katexCss: "katex.min.css.txt",
  mermaidMinJs: "mermaid.min.js.txt",
  pdfMinJs: "pdf.min.js.txt",
  pdfWorkerMinJs: "pdf.worker.min.js.txt",
  smilesDrawerMinJs: "smiles-drawer.min.js.txt",
  vegaEmbedMinJs: "vega-embed.min.js.txt",
  vegaLiteMinJs: "vega-lite.min.js.txt",
  vegaMinJs: "vega.min.js.txt",
};
const JS = Object.entries(FILES).filter(([key]) => key !== "katexCss");

describe("vendored web libraries", () => {
  it.each(Object.entries(FILES))("%s matches the hash the manifest pins", (key, file) => {
    expect(sha(read(file))).toBe(manifest.sha256[key]);
  });

  it("has an asset for every manifest entry and nothing else", () => {
    expect(Object.keys(manifest.sha256).sort()).toEqual(Object.keys(FILES).sort());
    expect(readdirSync(ASSETS).sort()).toEqual(Object.values(FILES).sort());
  });

  it("keeps no library in a TypeScript string module (DEAD-03)", () => {
    const modules = readdirSync(join(__dirname, "..")).filter((name) => name.endsWith(".ts"));
    expect(modules).toEqual([]);
  });

  it.each(JS)("%s is substantial", (_key, file) => {
    expect(read(file).length).toBeGreaterThan(1000);
  });

  it.each(JS)("%s contains no </script> sequence (safe to inline)", (_key, file) => {
    // The inline-script rendering path relies on this; the generator fails loudly
    // if a version bump introduces it, but this guards against a hand edit too.
    expect(read(file)).not.toMatch(/<\/script>/i);
  });

  it.each(JS)("%s contains no CDN host URL", (_key, file) => {
    // Vendored bundles must not reach back out to a CDN at runtime.
    expect(read(file)).not.toContain("cdnjs.cloudflare.com");
  });

  it("KaTeX CSS inlines woff2 fonts as data URIs and references no CDN", () => {
    const css = read(FILES.katexCss);
    expect(css).toContain("data:font/woff2;base64,");
    expect(css).not.toContain("cdn.jsdelivr.net");
    expect(css).not.toMatch(/url\(fonts\//);
  });

  it("pdf.js main + worker are both present and substantial", () => {
    expect(read(FILES.pdfMinJs).length).toBeGreaterThan(50_000);
    expect(read(FILES.pdfWorkerMinJs).length).toBeGreaterThan(500_000);
  });
});
