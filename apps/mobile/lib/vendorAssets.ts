import { useEffect, useState } from "react";

/**
 * The web libraries the sandboxed WebViews run (Mermaid, Vega, pdf.js, SmilesDrawer)
 * and the KaTeX CSS a printed reply uses, shipped as app assets and read on first
 * use. As TypeScript strings they were 6.1 MB of the JS bundle: carried by every
 * install and downloaded again with every update, while an asset is downloaded only
 * when it changes (code-health audit DEAD-03). They stay on the device, so the
 * previews work offline. scripts/vendor-cdn.mjs writes them; lib/vendor/manifest.json
 * pins their versions and hashes.
 */
/* eslint-disable @typescript-eslint/no-require-imports */
const SOURCES = {
  katexCss: require("@/assets/vendor/katex.min.css.txt"),
  mermaid: require("@/assets/vendor/mermaid.min.js.txt"),
  pdf: require("@/assets/vendor/pdf.min.js.txt"),
  pdfWorker: require("@/assets/vendor/pdf.worker.min.js.txt"),
  smilesDrawer: require("@/assets/vendor/smiles-drawer.min.js.txt"),
  vega: require("@/assets/vendor/vega.min.js.txt"),
  vegaLite: require("@/assets/vendor/vega-lite.min.js.txt"),
  vegaEmbed: require("@/assets/vendor/vega-embed.min.js.txt"),
} as const;
/* eslint-enable @typescript-eslint/no-require-imports */

type VendorName = keyof typeof SOURCES;
export type VendorTexts<N extends VendorName> = Record<N, string>;

const loading = new Map<VendorName, Promise<string>>();

async function read(name: VendorName): Promise<string> {
  // Required on first read, not at startup: nothing needs them before a preview does.
  /* eslint-disable @typescript-eslint/no-require-imports */
  const { Asset } = require("expo-asset") as typeof import("expo-asset");
  const { readAsStringAsync } = require("expo-file-system/legacy") as typeof import("expo-file-system/legacy");
  /* eslint-enable @typescript-eslint/no-require-imports */
  const asset = Asset.fromModule(SOURCES[name]);
  await asset.downloadAsync();
  return readAsStringAsync(asset.localUri ?? asset.uri);
}

/** A library's text, read from its asset once per run; a failed read is tried again next time. */
export function loadVendorText(name: VendorName): Promise<string> {
  const known = loading.get(name);
  if (known) return known;
  const text = read(name);
  loading.set(name, text);
  text.catch(() => {
    if (loading.get(name) === text) loading.delete(name);
  });
  return text;
}

export async function loadVendorTexts<N extends VendorName>(names: readonly N[]): Promise<VendorTexts<N>> {
  const texts = await Promise.all(names.map(loadVendorText));
  return Object.fromEntries(names.map((name, index) => [name, texts[index]])) as VendorTexts<N>;
}

/**
 * The libraries a preview needs, once read: `texts` is null until then, and stays
 * null with `failed` when they could not be read. Reads nothing while `enabled` is false.
 */
export function useVendorTexts<N extends VendorName>(
  names: readonly N[],
  enabled = true,
): { texts: VendorTexts<N> | null; failed: boolean } {
  const key = names.join(",");
  const [state, setState] = useState<{ key: string; texts: VendorTexts<N> | null; failed: boolean }>(
    { key, texts: null, failed: false },
  );
  useEffect(() => {
    if (!enabled) return;
    let current = true;
    loadVendorTexts(key.split(",") as N[]).then(
      (texts) => { if (current) setState({ key, texts, failed: false }); },
      () => { if (current) setState({ key, texts: null, failed: true }); },
    );
    return () => { current = false; };
  }, [key, enabled]);
  return state.key === key ? { texts: state.texts, failed: state.failed } : { texts: null, failed: false };
}
