import { getSessionGeneration } from "@/lib/auth";
import { api } from "@/lib/api";
import {
  fetchGalleryPage,
  fetchGalleryNextPage,
  getCachedGalleryPage,
  invalidateGalleryCache,
  isGalleryPageFresh,
  prefetchGallery,
  removeCachedGalleryItem,
  setGalleryPage,
} from "@/lib/cache/galleryListCache";
jest.mock("@/lib/auth", () => ({ getSessionGeneration: jest.fn(() => 0) }));
beforeEach(() => { (getSessionGeneration as jest.Mock).mockReturnValue(0); });

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


it("does not repopulate an invalidated cache from an earlier request", async () => {
  invalidateGalleryCache();
  let finish!: (value: unknown) => void;
  listAttachments.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const loading = fetchGalleryPage("token", "all", "");
  invalidateGalleryCache();
  finish({ items: sample.items, has_more: false });
  await loading;
  expect(getCachedGalleryPage("all", "")).toBeUndefined();
});

it("does not let an earlier next page replace a refreshed first page", async () => {
  setGalleryPage("all", "", { ...sample, hasMore: true });
  let finish!: (value: unknown) => void;
  listAttachments.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const more = fetchGalleryNextPage("token", "all", "");
  listAttachments.mockResolvedValueOnce({ items: [{ ...sample.items[0], id: "fresh" }], has_more: false });
  await fetchGalleryPage("token", "all", "", { force: true });
  finish({ items: [{ ...sample.items[0], id: "older" }], has_more: false });
  await more;
  expect(getCachedGalleryPage("all", "")?.items.map((row) => row.id)).toEqual(["fresh"]);
});

it("does not restore a deleted item when an earlier next page completes", async () => {
  setGalleryPage("all", "", { ...sample, hasMore: true });
  let finish!: (value: unknown) => void;
  listAttachments.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const more = fetchGalleryNextPage("token", "all", "");
  removeCachedGalleryItem("a");
  listAttachments.mockResolvedValueOnce({ items: [{ ...sample.items[0], id: "b" }], has_more: false });
  finish({ items: [{ ...sample.items[0], id: "b" }], has_more: false });
  await more;
  expect(getCachedGalleryPage("all", "")?.items.map((row) => row.id)).toEqual(["b"]);
});

it("never exposes a previous account's cached Library page", () => {
  setGalleryPage("all", "", sample);
  (getSessionGeneration as jest.Mock).mockReturnValue(1);
  expect(getCachedGalleryPage("all", "")).toBeUndefined();
});

it("advances the next offset even when a shifting page contains duplicate rows", async () => {
  invalidateGalleryCache();
  setGalleryPage("all", "", { ...sample, hasMore: true });
  listAttachments.mockResolvedValueOnce({ items: sample.items, has_more: true });
  await fetchGalleryNextPage("token", "all", "");
  listAttachments.mockResolvedValueOnce({ items: [], has_more: false });
  await fetchGalleryNextPage("token", "all", "");
  expect(listAttachments.mock.calls.at(-1)?.[1].offset).toBe(2);
});

it("refetches a shifted offset when a loaded file is deleted before the next query runs", async () => {
  invalidateGalleryCache();
  listAttachments.mockReset();
  const row = (id: string) => ({ ...sample.items[0]!, id });
  setGalleryPage("all", "", { items: [row("a")], hasMore: true });
  let finish!: (value: unknown) => void;
  listAttachments.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const more = fetchGalleryNextPage("token", "all", "");
  expect(listAttachments.mock.calls[0][1].offset).toBe(1);
  removeCachedGalleryItem("a");
  // DELETE wins on the server. The old offset of 1 now starts at c, skipping b.
  listAttachments.mockResolvedValueOnce({ items: [row("b"), row("c")], has_more: false });
  finish({ items: [row("c")], has_more: false });
  expect((await more)?.items.map((item) => item.id)).toEqual(["b", "c"]);
  expect(listAttachments.mock.calls[1][1].offset).toBe(0);
  expect(getCachedGalleryPage("all", "")?.items.map((item) => item.id)).toEqual(["b", "c"]);
});
