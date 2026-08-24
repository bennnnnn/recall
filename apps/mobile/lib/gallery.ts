import type { AttachmentListItem } from "@/lib/api";
import { isContextFresh } from "@/lib/cache/contextRefresh";

export const GALLERY_SEARCH_DEBOUNCE_MS = 300;

export type GalleryFilter = "all" | "generated" | "uploaded" | "files";

export type GalleryListParams = {
  category?: "images" | "files";
  source?: "upload" | "generated";
};

export function isGalleryImage(contentType: string): boolean {
  return contentType.startsWith("image/");
}

export function galleryPressAction(contentType: string): "view-image" | "share-file" {
  return isGalleryImage(contentType) ? "view-image" : "share-file";
}

export function galleryEmptyKey(
  filter: GalleryFilter,
): "gallery.empty" | "gallery.empty_files" | "gallery.empty_generated" | "gallery.empty_uploaded" {
  if (filter === "files") return "gallery.empty_files";
  if (filter === "generated") return "gallery.empty_generated";
  if (filter === "uploaded") return "gallery.empty_uploaded";
  return "gallery.empty";
}

export function galleryListParams(filter: GalleryFilter): GalleryListParams {
  if (filter === "files") return { category: "files" };
  if (filter === "generated") return { category: "images", source: "generated" };
  if (filter === "uploaded") return { category: "images", source: "upload" };
  return {};
}

export function galleryListCacheKey(filter: GalleryFilter, query: string): string {
  return `${filter}:${query.trim()}`;
}

export function shouldSkipGalleryFocusReload(opts: {
  lastFetchedAt: number | undefined;
  force?: boolean;
  now?: number;
}): boolean {
  if (opts.force) return false;
  return isContextFresh(opts.lastFetchedAt, opts.now);
}

export function galleryFileName(
  contentType: string,
  originalFilename?: string | null,
): string {
  const named = originalFilename?.trim().replace(/\\/g, "/").split("/").pop();
  if (named) return named;
  const subtype = contentType.split("/")[1]?.split("+")[0]?.split(";")[0]?.trim();
  if (!subtype) return "attachment";
  const ext = subtype.includes(".") ? subtype.slice(subtype.lastIndexOf(".") + 1) : subtype;
  return `attachment.${ext}`;
}

export function galleryThumbSize(listWidth: number, columns: number, gap: number): number {
  if (listWidth <= 0 || columns <= 0) return 1;
  return Math.max(1, Math.floor((listWidth - gap * (columns - 1)) / columns));
}

export function mergeGalleryItems(
  current: AttachmentListItem[],
  incoming: AttachmentListItem[],
  reset: boolean,
): AttachmentListItem[] {
  if (reset) return incoming;
  const seen = new Set(current.map((item) => item.id));
  return [...current, ...incoming.filter((item) => !seen.has(item.id))];
}
