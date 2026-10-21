// Integrity checks for the vendored web libraries (lib/vendor/*.txt). They lock
// in the invariants the generator (scripts/vendor-cdn.mjs) guarantees, so an
// empty or hand-edited file, a library left out of the app, or a re-introduced
// CDN URL is caught at test time rather than at runtime (blank WebView offline).

// The lib test project includes Jest types, but no global Node type package.
declare const __dirname: string;
const { createHash } = jest.requireActual<{
  createHash(name: string): { update(value: string): { digest(encoding: string): string } };
}>("node:crypto");
const { readdirSync, readFileSync } = jest.requireActual<{
  readdirSync(path: string): string[];
  readFileSync(path: string, encoding: "utf8"): string;
}>("node:fs");
const { join } = jest.requireActual<{ join(...parts: string[]): string }>("node:path");

const VENDOR_DIR = join(__dirname, "..");
const read = (file: string): string => readFileSync(join(VENDOR_DIR, file), "utf8");
const manifest = JSON.parse(read("manifest.json")) as { sha256: Record<string, string> };

/** Each file, by the name the manifest records its hash under. */
const FILES: [string, string][] = [
  ["katexCss", "katex.min.css.txt"],
  ["mermaidMinJs", "mermaid.min.js.txt"],
  ["vegaMinJs", "vega.min.js.txt"],
  ["vegaLiteMinJs", "vega-lite.min.js.txt"],
  ["vegaEmbedMinJs", "vega-embed.min.js.txt"],
  ["pdfMinJs", "pdf.min.js.txt"],
  ["pdfWorkerMinJs", "pdf.worker.min.js.txt"],
  ["smilesDrawerMinJs", "smiles-drawer.min.js.txt"],
];
const SCRIPTS = FILES.filter(([, file]) => file.endsWith(".js.txt")).map(([, file]) => [file]);

describe("vendored web libraries", () => {
  it.each(FILES)("%s is the file scripts/vendor-cdn.mjs wrote", (name, file) => {
    const sha = createHash("sha256").update(read(file)).digest("hex");
    expect(sha.slice(0, 16)).toBe(manifest.sha256[name]);
  });

  it("ships every vendored file as an asset, and only those", () => {
    // Metro bundles an asset only when lib/vendorAssets.ts requires it.
    const assets = readFileSync(join(VENDOR_DIR, "..", "vendorAssets.ts"), "utf8");
    const shipped = [...assets.matchAll(/require\("@\/lib\/vendor\/([^"]+)"\)/g)].map((m) => m[1]);
    const files = readdirSync(VENDOR_DIR).filter((file) => file.endsWith(".txt"));
    expect(shipped.sort()).toEqual(files.sort());
    expect(files.sort()).toEqual(FILES.map(([, file]) => file).sort());
  });

  it.each(SCRIPTS)("%s is a substantial script", (file) => {
    expect(read(file).length).toBeGreaterThan(1000);
  });

  it.each(SCRIPTS)("%s contains no </script> sequence (safe to inline)", (file) => {
    // The pages inline these scripts; the generator fails loudly if a version
    // bump introduces the sequence, and this guards against a hand edit too.
    expect(read(file)).not.toMatch(/<\/script>/i);
  });

  it.each(SCRIPTS)("%s contains no CDN host URL", (file) => {
    // Vendored bundles must not reach back out to a CDN at runtime.
    expect(read(file)).not.toContain("cdnjs.cloudflare.com");
  });

  it("inlines KaTeX's woff2 fonts as data URIs and references no CDN", () => {
    const css = read("katex.min.css.txt");
    expect(css).toContain("data:font/woff2;base64,");
    expect(css).not.toContain("cdn.jsdelivr.net");
    expect(css).not.toMatch(/url\(fonts\//);
  });

  it("has pdf.js main and worker, both substantial", () => {
    expect(read("pdf.min.js.txt").length).toBeGreaterThan(50_000);
    expect(read("pdf.worker.min.js.txt").length).toBeGreaterThan(500_000);
  });
});
