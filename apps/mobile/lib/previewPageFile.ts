import { CryptoDigestAlgorithm, digestStringAsync } from "expo-crypto";
import {
  cacheDirectory,
  deleteAsync,
  getInfoAsync,
  makeDirectoryAsync,
  moveAsync,
  readDirectoryAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

import type { PreviewPage } from "@/lib/previewPage";
import {
  readVendorLibraries,
  vendorLibraryHash,
  type VendorLibrary,
} from "@/lib/vendorAssets";

const PAGE_DIRECTORY = "preview-pages/";
const VERSION_CHARS = 16;
/** What follows `<page name>-` in a version's file name, or in its partial write. */
const VERSION_FILE = /^[0-9a-f]+\.html(\.part)?$/;

type PageFile = { written: Promise<string>; uri: string | null };

/**
 * This run's page files. Keyed by the page object, so a page whose module
 * reloads in development (Fast Refresh) is written again.
 */
const pageFiles = new WeakMap<PreviewPage<VendorLibrary>, PageFile>();

/**
 * The page's file in the cache directory, written once per version: the name
 * carries a hash of the page built around its libraries' content hashes, so a
 * change to the template or to a library gets a new file and an unchanged page
 * is never read or written again. Every WebView of that kind loads this file.
 */
export function previewPageFile<L extends VendorLibrary>(page: PreviewPage<L>): Promise<string> {
  const known = pageFiles.get(page);
  if (known) return known.written;
  const entry: PageFile = { written: writePageFile(page), uri: null };
  entry.written.then(
    (uri) => {
      entry.uri = uri;
    },
    () => {
      if (pageFiles.get(page) === entry) pageFiles.delete(page);
    },
  );
  pageFiles.set(page, entry);
  return entry.written;
}

/** The page's file once this run has it, so a WebView can mount without waiting. */
export function readyPreviewPageFile(page: PreviewPage<VendorLibrary>): string | null {
  return pageFiles.get(page)?.uri ?? null;
}

/** A WebView could not load the file (the cache was cleared): write it again next time. */
export function forgetPreviewPageFile(page: PreviewPage<VendorLibrary>): void {
  pageFiles.delete(page);
}

async function writePageFile<L extends VendorLibrary>(page: PreviewPage<L>): Promise<string> {
  if (!cacheDirectory) throw new Error("Storage unavailable.");
  const directory = `${cacheDirectory}${PAGE_DIRECTORY}`;
  const hashes = Object.fromEntries(
    page.libraries.map((library) => [library, vendorLibraryHash(library)]),
  ) as Record<L, string>;
  const digest = await digestStringAsync(CryptoDigestAlgorithm.SHA256, page.build(hashes));
  const name = `${page.name}-${digest.slice(0, VERSION_CHARS)}.html`;
  const uri = `${directory}${name}`;
  if ((await getInfoAsync(uri)).exists) return uri;

  const html = page.build(await readVendorLibraries(page.libraries));
  await makeDirectoryAsync(directory, { intermediates: true });
  // Written beside its final name, then moved: a run killed mid-write never
  // leaves a short page that a later run would take for a finished one.
  const partial = `${uri}.part`;
  await writeAsStringAsync(partial, html);
  await moveAsync({ from: partial, to: uri });
  void removeOtherVersions(directory, page.name, name);
  return uri;
}

/** Earlier versions of the page, and any partial write, once the new one is in place. */
async function removeOtherVersions(directory: string, pageName: string, keep: string): Promise<void> {
  const names = await readDirectoryAsync(directory).catch(() => [] as string[]);
  const prefix = `${pageName}-`;
  const stale = names.filter(
    (name) => name !== keep && name.startsWith(prefix) && VERSION_FILE.test(name.slice(prefix.length)),
  );
  await Promise.allSettled(stale.map((name) => deleteAsync(`${directory}${name}`, { idempotent: true })));
}
