import { request } from "@/lib/api/client";
import { clearLinkPreviewCache, fetchLinkPreview } from "@/lib/linkPreview";

jest.mock("@/lib/api/client", () => ({ request: jest.fn() }));
jest.mock("@/lib/auth", () => ({ getToken: jest.fn(async () => "token") }));

const fetchPreview = request as jest.Mock;
const preview = { url: "https://a.example", title: "A", description: null, domain: "a.example" };

beforeEach(() => {
  clearLinkPreviewCache();
  fetchPreview.mockReset();
  jest.restoreAllMocks();
});

it("sends one request for two cards showing the same link at once (NET-19)", async () => {
  fetchPreview.mockResolvedValue(preview);
  const [first, second] = await Promise.all([
    fetchLinkPreview("https://a.example"),
    fetchLinkPreview("https://a.example"),
  ]);
  expect(first).toEqual(preview);
  expect(second).toEqual(preview);
  expect(fetchPreview).toHaveBeenCalledTimes(1);
  // And keeps it.
  await fetchLinkPreview("https://a.example");
  expect(fetchPreview).toHaveBeenCalledTimes(1);
});

it("does not ask again for a link that failed, until a while has passed", async () => {
  const now = Date.now();
  const clock = jest.spyOn(Date, "now").mockReturnValue(now);
  fetchPreview.mockRejectedValueOnce(new Error("429")).mockResolvedValue(preview);
  await expect(fetchLinkPreview("https://a.example")).rejects.toThrow();
  // The card scrolls back into view.
  await expect(fetchLinkPreview("https://a.example")).rejects.toThrow("preview failed");
  expect(fetchPreview).toHaveBeenCalledTimes(1);

  clock.mockReturnValue(now + 5 * 60_000);
  await expect(fetchLinkPreview("https://a.example")).resolves.toEqual(preview);
  expect(fetchPreview).toHaveBeenCalledTimes(2);
});

it("does not let a request from before sign-out fill the next account's cache", async () => {
  let finish!: (value: unknown) => void;
  fetchPreview.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const before = fetchLinkPreview("https://a.example");
  await Promise.resolve();
  clearLinkPreviewCache();
  finish(preview);
  await before;
  fetchPreview.mockResolvedValueOnce({ ...preview, title: "B" });
  await expect(fetchLinkPreview("https://a.example")).resolves.toMatchObject({ title: "B" });
  expect(fetchPreview).toHaveBeenCalledTimes(2);
});
