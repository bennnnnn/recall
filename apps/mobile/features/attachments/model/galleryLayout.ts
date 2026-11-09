/**
 * Persist Library grid vs column layout. Not a secret — filesystem, not Keychain.
 */

import { createFilePref } from "@/lib/filePrefs";

export type GalleryLayout = "grid" | "column";

function normalizeGalleryLayout(raw: string | null | undefined): GalleryLayout {
  return raw === "column" ? "column" : "grid";
}

const layoutPref = createFilePref<GalleryLayout>("recall.gallery-layout.txt", normalizeGalleryLayout);

/** Last known value this session; "grid" before the first read. */
export function peekGalleryLayout(): GalleryLayout {
  return layoutPref.peek() ?? "grid";
}

export const { get: getGalleryLayout, set: setGalleryLayout, reset: resetGalleryLayoutForTest } = layoutPref;
