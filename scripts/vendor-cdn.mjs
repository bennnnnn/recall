#!/usr/bin/env node
/**
 * Vendor CDN-served JS assets into local files so the sandboxed WebView
 * renderers (Mermaid, Vega, pdf.js, SmilesDrawer) work fully offline — no
 * runtime CDN fetch, tighter CSP, faster first render. Versions are pinned.
 *
 * Output: apps/mobile/lib/vendor/*.txt  (committed; this script regenerates them).
 * Each file is the library's own text. Metro ships them as assets beside the JS
 * bundle ("txt" in apps/mobile/metro.config.js); apps/mobile/lib/vendorAssets.ts
 * names each one and reads it at run time.
 *
 * Usage: node scripts/vendor-cdn.mjs
 */
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const VENDOR_DIR = join(process.cwd(), "apps/mobile/lib/vendor");
const TMP_DIR = join("/tmp", "recall-vendor-dl");
mkdirSync(VENDOR_DIR, { recursive: true });
mkdirSync(TMP_DIR, { recursive: true });

const VERSIONS = {
  // Pinned exactly to the committed bundle version (MathJax's internal
  // version is 3.2.1). A floating "3" would silently pull whatever 3.x
  // jsDelivr serves on the next vendor regen. Bump deliberately.
  mermaid: "10",
  vega: "5",
  vegaLite: "5",
  vegaEmbed: "6",
  pdfjs: "3.11.174",
  smilesDrawer: "2.1.7",
};

async function download(url, dest) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch ${url} -> ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  writeFileSync(dest, buf);
  return buf;
}

/** Each library's file in lib/vendor, by the name the manifest records its hash under. */
const VENDOR_FILES = {
  mermaidMinJs: "mermaid.min.js.txt",
  vegaMinJs: "vega.min.js.txt",
  vegaLiteMinJs: "vega-lite.min.js.txt",
  vegaEmbedMinJs: "vega-embed.min.js.txt",
  pdfMinJs: "pdf.min.js.txt",
  pdfWorkerMinJs: "pdf.worker.min.js.txt",
  smilesDrawerMinJs: "smiles-drawer.min.js.txt",
};

/** Write a library's text as is: the app reads the file, so nothing may wrap it. */
function writeVendorFile(name, content, comment) {
  writeFileSync(join(VENDOR_DIR, VENDOR_FILES[name]), content);
  console.log(`${VENDOR_FILES[name]}: ${comment} ${(content.length / 1024).toFixed(0)} KB`);
}

async function main() {
  // 2. Mermaid
  const mermaidBuf = await download(`https://cdn.jsdelivr.net/npm/mermaid@${VERSIONS.mermaid}/dist/mermaid.min.js`, join(TMP_DIR, "mermaid.min.js"));
  writeVendorFile("mermaidMinJs", mermaidBuf.toString("utf8"), `Mermaid ${VERSIONS.mermaid} min.`);

  // 4. Vega stack
  const vegaBuf = await download(`https://cdn.jsdelivr.net/npm/vega@${VERSIONS.vega}`, join(TMP_DIR, "vega.min.js"));
  writeVendorFile("vegaMinJs", vegaBuf.toString("utf8"), `Vega ${VERSIONS.vega} min.`);
  const vegaLiteBuf = await download(`https://cdn.jsdelivr.net/npm/vega-lite@${VERSIONS.vegaLite}`, join(TMP_DIR, "vega-lite.min.js"));
  writeVendorFile("vegaLiteMinJs", vegaLiteBuf.toString("utf8"), `Vega-Lite ${VERSIONS.vegaLite} min.`);
  const vegaEmbedBuf = await download(`https://cdn.jsdelivr.net/npm/vega-embed@${VERSIONS.vegaEmbed}`, join(TMP_DIR, "vega-embed.min.js"));
  writeVendorFile("vegaEmbedMinJs", vegaEmbedBuf.toString("utf8"), `Vega-Embed ${VERSIONS.vegaEmbed} min.`);

  // 5. pdf.js (main + worker)
  const pdfBase = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${VERSIONS.pdfjs}`;
  const pdfMainBuf = await download(`${pdfBase}/pdf.min.js`, join(TMP_DIR, "pdf.min.js"));
  writeVendorFile("pdfMinJs", pdfMainBuf.toString("utf8"), `pdf.js ${VERSIONS.pdfjs} main.`);
  const pdfWorkerBuf = await download(`${pdfBase}/pdf.worker.min.js`, join(TMP_DIR, "pdf.worker.min.js"));
  writeVendorFile("pdfWorkerMinJs", pdfWorkerBuf.toString("utf8"), `pdf.js ${VERSIONS.pdfjs} worker (loaded via Blob URL at runtime).`);

  // 6. SmilesDrawer (chemistry) — browserify bundle; WebView loads via require(1) shim.
  const smilesUrl =
    `https://cdn.jsdelivr.net/npm/smiles-drawer@${VERSIONS.smilesDrawer}/dist/smiles-drawer.min.js`;
  const smilesBuf = await download(smilesUrl, join(TMP_DIR, "smiles-drawer.min.js"));
  const smilesJs = smilesBuf
    .toString("utf8")
    .replace(/\n?\/\/# sourceMappingURL=.*$/m, "");
  writeVendorFile(
    "smilesDrawerMinJs",
    smilesJs,
    `smiles-drawer ${VERSIONS.smilesDrawer} min (browserify — load via require(1) shim).`,
  );

  // Manifest for traceability
  const allJs = [
    ["mermaidMinJs", mermaidBuf.toString("utf8")],
    ["vegaMinJs", vegaBuf.toString("utf8")],
    ["vegaLiteMinJs", vegaLiteBuf.toString("utf8")],
    ["vegaEmbedMinJs", vegaEmbedBuf.toString("utf8")],
    ["pdfMinJs", pdfMainBuf.toString("utf8")],
    ["pdfWorkerMinJs", pdfWorkerBuf.toString("utf8")],
    ["smilesDrawerMinJs", smilesJs],
  ];
  for (const [name, src] of allJs) {
    if (/<\/script>/i.test(src)) {
      throw new Error(
        `Vendored JS ${name} contains a "</script>" sequence — the inline-` +
        `script rendering path would break. Inspect the upgrade and handle it ` +
        `(e.g. split the sequence) before re-running.`,
      );
    }
  }
  const manifest = {
    generatedAt: new Date().toISOString(),
    versions: VERSIONS,
    sha256: {
        mermaidMinJs: sha(mermaidBuf),
      vegaMinJs: sha(vegaBuf),
      vegaLiteMinJs: sha(vegaLiteBuf),
      vegaEmbedMinJs: sha(vegaEmbedBuf),
      pdfMinJs: sha(pdfMainBuf),
      pdfWorkerMinJs: sha(pdfWorkerBuf),
      smilesDrawerMinJs: sha(smilesJs),
    },
  };
  writeFileSync(join(VENDOR_DIR, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
  console.log("Vendor generation complete:", VENDOR_DIR);
}

function sha(buf) {
  return createHash("sha256").update(buf).digest("hex").slice(0, 16);
}

main().catch((e) => { console.error(e); process.exit(1); });
