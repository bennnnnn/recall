export type GalleryFilter = "all" | "images" | "files";

export function isGalleryImage(contentType: string): boolean {
  return contentType.startsWith("image/");
}

export function galleryPressAction(contentType: string): "view-image" | "share-file" {
  return isGalleryImage(contentType) ? "view-image" : "share-file";
}

export function galleryEmptyKey(filter: GalleryFilter): "gallery.empty" | "gallery.empty_files" {
  return filter === "files" ? "gallery.empty_files" : "gallery.empty";
}

export function galleryFileName(contentType: string): string {
  const subtype = contentType.split("/")[1]?.split("+")[0]?.split(";")[0]?.trim();
  if (!subtype) return "attachment";
  const ext = subtype.includes(".") ? subtype.slice(subtype.lastIndexOf(".") + 1) : subtype;
  return `attachment.${ext}`;
}

export function galleryThumbSize(listWidth: number, columns: number, gap: number): number {
  if (listWidth <= 0 || columns <= 0) return 1;
  return Math.max(1, Math.floor((listWidth - gap * (columns - 1)) / columns));
}
