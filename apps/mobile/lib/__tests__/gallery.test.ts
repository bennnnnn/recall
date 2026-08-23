import {
  galleryEmptyKey,
  galleryFileName,
  galleryPressAction,
  galleryThumbSize,
  isGalleryImage,
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
    expect(galleryEmptyKey("images")).toBe("gallery.empty");
  });

  it("derives a share filename from the content type", () => {
    expect(galleryFileName("application/pdf")).toBe("attachment.pdf");
    expect(galleryFileName("image/png")).toBe("attachment.png");
    expect(galleryFileName("application/vnd.openxmlformats-officedocument.wordprocessingml.document")).toBe(
      "attachment.document",
    );
  });

  it("fills the row across three columns", () => {
    expect(galleryThumbSize(390 - 32, 3, 12)).toBe(111);
    expect(galleryThumbSize(0, 3, 12)).toBe(1);
  });
});
