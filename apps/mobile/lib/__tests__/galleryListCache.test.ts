import { api } from "@/lib/api";
import {
  fetchGalleryPage,
  getCachedGalleryPage,
  invalidateGalleryCache,
  isGalleryPageFresh,
  prefetchGallery,
  removeCachedGalleryItem,
  setGalleryPage,
} from "@/lib/cache/galleryListCache";

jest.mock("@/lib/api", () => ({
  api: {
    listAttachments: jest.fn(),
  },
}));

const listAttachments = api.listAttachments as jest.Mock;

const sample = {
  items: [
    {
      id: "a",
      content_type: "image/png",
      size_bytes: 12,
      download_url: "/attachments/a/file",
      source: "upload" as const,
      created_at: "2026-01-01T00:00:00.000Z",
    },
  ],
  hasMore: false,
};

describe("galleryListCache", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    invalidateGalleryCache();
  });

  it("returns a fresh page without refetching", async () => {
    setGalleryPage("all", "", sample);
    expect(isGalleryPageFresh("all", "")).toBe(true);
    expect(getCachedGalleryPage("all", "")).toEqual(sample);

    const result = await fetchGalleryPage("token", "all", "");
    expect(result).toEqual(sample);
    expect(listAttachments).not.toHaveBeenCalled();
  });

  it("strips an id from every cached tab", () => {
    setGalleryPage("all", "", {
      items: [sample.items[0]!, { ...sample.items[0]!, id: "b" }],
      hasMore: false,
    });
    setGalleryPage("files", "", { items: [sample.items[0]!], hasMore: false });
    removeCachedGalleryItem("a");
    expect(getCachedGalleryPage("all", "")?.items.map((row) => row.id)).toEqual(["b"]);
    expect(getCachedGalleryPage("files", "")?.items).toEqual([]);
  });

  it("prefetch skips when All is already fresh", () => {
    setGalleryPage("all", "", sample);
    prefetchGallery("token");
    expect(listAttachments).not.toHaveBeenCalled();
  });
});
