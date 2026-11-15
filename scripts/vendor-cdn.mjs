#!/usr/bin/env node
/**
 * Vendor CDN-served JS assets into local files so the sandboxed WebView
 * renderers (Mermaid, Vega, pdf.js, SmilesDrawer) work fully offline — no
 * runtime CDN fetch, tighter CSP, faster first render.
 *
 * Each library is the file its npm package ships (the same bytes jsDelivr and
 * cdnjs serve for that version), at the exact version pinned below. `npm pack`
 * fetches the package, and the script refuses the tarball unless its sha512
 * is the one pinned beside that version, before reading anything from it. So
 * a regen writes only the bytes this file names: a moved tag, a new release or
 * a tampered mirror stops the script instead of landing in the app. To bump a
 * library, change its version and integrity together
 * (`npm view <name>@<version> dist.integrity`).
 *
 * Output: apps/mobile/lib/vendor/*.txt  (committed; this script regenerates them).
 * Each file is the library's own text. Metro ships them as assets beside the JS
 * bundle ("txt" in apps/mobile/metro.config.js); apps/mobile/lib/vendorAssets.ts
 * names each one and reads it at run time.
 *
 * Usage: node scripts/vendor-cdn.mjs
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";

const VENDOR_DIR = join(process.cwd(), "apps/mobile/lib/vendor");

/** Each package, by the name the manifest records its version under, with its tarball's integrity. */
const PACKAGES = {
  mermaid: {
    name: "mermaid",
    version: "10.9.6",
    integrity: "sha512-XRjjRaI4aPCAMpVaOhxIwLYdx3U4Cb6mN0M268ggFAfFRqsvyFW8zxWbEZazN/mPkqsVWThb0oa1UawWK+XMNg==",
  },
  vega: {
    name: "vega",
    version: "5.33.1",
    integrity: "sha512-1fArfVDUqVbb5z8n+/nVQb+VNBzx8svY6CrsyTK4Ujm4yrd9I1auoKxBAPXLCavY1LcrbHUskQbGUP8gXOzyQw==",
  },
  vegaLite: {
    name: "vega-lite",
    version: "5.23.0",
    integrity: "sha512-l4J6+AWE3DIjvovEoHl2LdtCUkfm4zs8Xxx7INwZEAv+XVb6kR6vIN1gt3t2gN2gs/y4DYTs/RPoTeYAuEg6mA==",
  },
  vegaEmbed: {
    name: "vega-embed",
    version: "6.29.0",
    integrity: "sha512-PmlshTLtLFLgWtF/b23T1OwX53AugJ9RZ3qPE2c01VFAbgt3/GSNI/etzA/GzdrkceXFma+FDHNXUppKuM0U6Q==",
  },
  pdfjs: {
    name: "pdfjs-dist",
    version: "3.11.174",
    integrity: "sha512-TdTZPf1trZ8/UFu5Cx/GXB7GZM30LT+wWUNfsi6Bq8ePLnb+woNKtDymI2mxZYBpMbonNFqKmiz684DIfnd8dA==",
  },
  smilesDrawer: {
    name: "smiles-drawer",
    version: "2.1.7",
    integrity: "sha512-gApm5tsWrAYDkjbGYQb5OhwIyHvtM2kIO40DfATaOV0DPm0wA63yn4Ow7us27BT49lDdU9busCOPN9fpyonzaA==",
  },
};

/** Each library's file in lib/vendor, by the name the manifest records its hash under, and where its package keeps it. */
const VENDOR_FILES = {
  mermaidMinJs: { file: "mermaid.min.js.txt", pkg: "mermaid", path: "dist/mermaid.min.js", note: "Mermaid min." },
  vegaMinJs: { file: "vega.min.js.txt", pkg: "vega", path: "build/vega.min.js", note: "Vega min." },
  vegaLiteMinJs: { file: "vega-lite.min.js.txt", pkg: "vegaLite", path: "build/vega-lite.min.js", note: "Vega-Lite min." },
  vegaEmbedMinJs: { file: "vega-embed.min.js.txt", pkg: "vegaEmbed", path: "build/vega-embed.min.js", note: "Vega-Embed min." },
  pdfMinJs: { file: "pdf.min.js.txt", pkg: "pdfjs", path: "build/pdf.min.js", note: "pdf.js main." },
  pdfWorkerMinJs: {
    file: "pdf.worker.min.js.txt",
    pkg: "pdfjs",
    path: "build/pdf.worker.min.js",
    note: "pdf.js worker (loaded via Blob URL at runtime).",
  },
  // SmilesDrawer (chemistry) — browserify bundle; WebView loads via require(1) shim.
  // Its source map is not shipped, so the comment pointing at it goes.
  smilesDrawerMinJs: {
    file: "smiles-drawer.min.js.txt",
    pkg: "smilesDrawer",
    path: "dist/smiles-drawer.min.js",
    note: "smiles-drawer min (browserify — load via require(1) shim).",
    edit: (src) => src.replace(/\n?\/\/# sourceMappingURL=.*$/m, ""),
  },
};

/** Fetch a package with npm and return its tarball, refused unless it is the pinned one. */
function packVerified({ name, version, integrity }, dir) {
  const packed = execFileSync(
    "npm",
    ["pack", `${name}@${version}`, "--ignore-scripts", "--json", "--pack-destination", dir],
    { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] },
  );
  // One read: the bytes checked here are the bytes the files come from.
  const tarball = readFileSync(join(dir, JSON.parse(packed)[0].filename));
  const actual = `sha512-${createHash("sha512").update(tarball).digest("base64")}`;
  if (actual !== integrity) {
    throw new Error(`${name}@${version}: tarball is ${actual}, pinned ${integrity}. Not vendoring it.`);
  }
  return tarball;
}

/** One file's text out of a verified npm tarball (gzipped ustar, every entry under package/). */
function readEntry(tarball, path) {
  const tar = gunzipSync(tarball);
  const text = (at, length) => tar.toString("utf8", at, at + length).replace(/\0.*$/s, "");
  for (let at = 0; at + 512 <= tar.length; ) {
    const name = text(at, 100);
    if (!name) break;
    const prefix = text(at + 345, 155);
    const size = parseInt(text(at + 124, 12).trim() || "0", 8);
    at += 512;
    if ((prefix ? `${prefix}/${name}` : name) === `package/${path}`) return tar.toString("utf8", at, at + size);
    at += Math.ceil(size / 512) * 512;
  }
  throw new Error(`package/${path} is not in the tarball`);
}

function main() {
  mkdirSync(VENDOR_DIR, { recursive: true });
  const work = mkdtempSync(join(tmpdir(), "recall-vendor-"));
  const files = [];
  try {
    const tarballs = Object.fromEntries(
      Object.entries(PACKAGES).map(([key, pkg]) => [key, packVerified(pkg, work)]),
    );
    for (const [name, spec] of Object.entries(VENDOR_FILES)) {
      const src = readEntry(tarballs[spec.pkg], spec.path);
      files.push([name, spec, spec.edit ? spec.edit(src) : src]);
    }
  } finally {
    rmSync(work, { recursive: true, force: true });
  }

  // Checked before anything is written, so a bad upgrade leaves lib/vendor as it was.
  for (const [name, , src] of files) {
    if (/<\/script>/i.test(src)) {
      throw new Error(
        `Vendored JS ${name} contains a "</script>" sequence — the inline-` +
        `script rendering path would break. Inspect the upgrade and handle it ` +
        `(e.g. split the sequence) before re-running.`,
      );
    }
  }

  // Write a library's text as is: the app reads the file, so nothing may wrap it.
  for (const [, spec, src] of files) {
    const { version } = PACKAGES[spec.pkg];
    writeFileSync(join(VENDOR_DIR, spec.file), src);
    console.log(`${spec.file}: ${spec.note} ${version}, ${(src.length / 1024).toFixed(0)} KB`);
  }

  // Manifest for traceability
  const manifest = {
    generatedAt: new Date().toISOString(),
    versions: Object.fromEntries(Object.entries(PACKAGES).map(([key, { version }]) => [key, version])),
    sha256: Object.fromEntries(files.map(([name, , src]) => [name, sha(src)])),
  };
  writeFileSync(join(VENDOR_DIR, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
  console.log("Vendor generation complete:", VENDOR_DIR);
}

function sha(text) {
  return createHash("sha256").update(text).digest("hex").slice(0, 16);
}

try {
  main();
} catch (e) {
  console.error(e);
  process.exit(1);
}
