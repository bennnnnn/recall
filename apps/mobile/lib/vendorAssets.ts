/* eslint-disable @typescript-eslint/no-require-imports -- Metro assets: "txt" is in metro.config.js assetExts */
/**
 * The web libraries the preview WebViews run, vendored into lib/vendor by
 * scripts/vendor-cdn.mjs. Metro ships them as assets beside the JS bundle,
 * not as strings inside it: the bundle stays small, and an over-the-air update
 * downloads a library only when it changed. In development they come from
 * Metro; in a build, from the app or the update that brought them.
 */
import { Asset } from "expo-asset";
import { readAsStringAsync } from "expo-file-system/legacy";

export type VendorLibrary =
  | "katexCss"
  | "mermaid"
  | "pdf"
  | "pdfWorker"
  | "smilesDrawer"
  | "vega"
  | "vegaEmbed"
  | "vegaLite";

const VENDOR_ASSETS: Record<VendorLibrary, number> = {
  katexCss: require("@/lib/vendor/katex.min.css.txt"),
  mermaid: require("@/lib/vendor/mermaid.min.js.txt"),
  pdf: require("@/lib/vendor/pdf.min.js.txt"),
  pdfWorker: require("@/lib/vendor/pdf.worker.min.js.txt"),
  smilesDrawer: require("@/lib/vendor/smiles-drawer.min.js.txt"),
  vega: require("@/lib/vendor/vega.min.js.txt"),
  vegaEmbed: require("@/lib/vendor/vega-embed.min.js.txt"),
  vegaLite: require("@/lib/vendor/vega-lite.min.js.txt"),
};

/** The library's content hash, from the bundle's asset table: nothing is read. */
export function vendorLibraryHash(library: VendorLibrary): string {
  const { hash } = Asset.fromModule(VENDOR_ASSETS[library]);
  if (!hash) throw new Error(`The vendored ${library} has no content hash.`);
  return hash;
}

/** The library's source text. */
export async function readVendorLibrary(library: VendorLibrary): Promise<string> {
  const asset = await Asset.fromModule(VENDOR_ASSETS[library]).downloadAsync();
  if (!asset.localUri) throw new Error(`The vendored ${library} is not on the device.`);
  return readAsStringAsync(asset.localUri);
}

/** Several libraries' sources, by name. */
export async function readVendorLibraries<L extends VendorLibrary>(
  libraries: readonly L[],
): Promise<Record<L, string>> {
  const sources = await Promise.all(libraries.map(readVendorLibrary));
  return Object.fromEntries(libraries.map((library, index) => [library, sources[index]])) as Record<L, string>;
}
