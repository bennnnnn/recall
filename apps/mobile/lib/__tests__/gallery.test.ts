import {
  galleryEmptyKey,
  galleryFileName,
  galleryListCacheKey,
  galleryListParams,
  galleryPressAction,
  galleryThumbSize,
  isGalleryImage,
  mergeGalleryItems,
  shouldSkipGalleryFocusReload,
} from "@/lib/gallery";

describe("gallery helpers", () => {
  it("opens images in the viewer and shares files", () => {
    expect(isGalleryImage("image/png")).toBe(true);
    expect(isGalleryImage("application/pdf")).toBe(false);
    expect(galleryPressAction("image/jpeg")).toBe("view-image");
    expect(galleryPressAction("application/pdf")).toBe("share-file");
    expect(galleryPressAction("text/plain")).toBe("share-file");
  });

  it("uses file empty copy on the files tab", () => {
    expect(galleryEmptyKey("files")).toBe("gallery.empty_files");
    expect(galleryEmptyKey("all")).toBe("gallery.empty");
    expect(galleryEmptyKey("generated")).toBe("gallery.empty_generated");
    expect(galleryEmptyKey("uploaded")).toBe("gallery.empty_uploaded");
  });

  it("maps tabs to category and source query params", () => {
    expect(galleryListParams("all")).toEqual({});
    expect(galleryListParams("generated")).toEqual({
      category: "images",
      source: "generated",
    });
    expect(galleryListParams("uploaded")).toEqual({
      category: "images",
      source: "upload",
    });
    expect(galleryListParams("files")).toEqual({ category: "files" });
  });

  it("derives a share filename from the content type", () => {
    expect(galleryFileName("application/pdf")).toBe("attachment.pdf");
    expect(galleryFileName("image/png")).toBe("attachment.png");
    expect(galleryFileName("application/pdf", "notes.pdf")).toBe("notes.pdf");
    expect(galleryFileName("application/pdf", "folder/notes.pdf")).toBe("notes.pdf");
    expect(galleryFileName("application/vnd.openxmlformats-officedocument.wordprocessingml.document")).toBe(
      "attachment.document",
    );
  });

  it("fills the row across three columns", () => {
    expect(galleryThumbSize(390 - 32, 3, 12)).toBe(111);
    expect(galleryThumbSize(0, 3, 12)).toBe(1);
  });

  it("dedupes ids when appending a gallery page", () => {
    const current = [{ id: "a" }, { id: "b" }] as never;
    const incoming = [{ id: "b" }, { id: "c" }] as never;
    expect(mergeGalleryItems(current, incoming, false).map((item) => item.id)).toEqual([
      "a",
      "b",
      "c",
    ]);
    expect(mergeGalleryItems(current, incoming, true).map((item) => item.id)).toEqual([
      "b",
      "c",
    ]);
  });

  it("skips a fresh gallery focus reload for the same filter and query", () => {
    expect(galleryListCacheKey("all", "  cat ")).toBe("all:cat");
    const now = Date.now();
    expect(shouldSkipGalleryFocusReload({ lastFetchedAt: now, now })).toBe(true);
    expect(shouldSkipGalleryFocusReload({ lastFetchedAt: now, force: true, now })).toBe(
      false,
    );
    expect(
      shouldSkipGalleryFocusReload({ lastFetchedAt: now - 21_000, now }),
    ).toBe(false);
  });
});
