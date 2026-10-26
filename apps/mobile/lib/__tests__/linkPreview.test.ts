import { request } from "@/lib/api/client";
import { ApiRequestError } from "@/lib/api/errorBody";
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

/** The server's busy refusal (modules/link_preview/api.py): 429 `link_preview_busy`. */
function busy(retryAfterMs: number | null): ApiRequestError {
  const body = JSON.stringify({ detail: { code: "link_preview_busy", message: "Too many previews loading. Try again shortly." } });
  return new ApiRequestError(429, body, retryAfterMs);
}

describe("a busy refusal", () => {
  it.each([
    ["for its Retry-After", 8_000, 8_000],
    ["for the server's stated 8 s without the header", null, 8_000],
    ["for at most a minute, whatever the header says", 5 * 60_000, 60_000],
  ])("is remembered %s, then asked for again once", async (_name, retryAfterMs, waitMs) => {
    const now = Date.now();
    const clock = jest.spyOn(Date, "now").mockReturnValue(now);
    fetchPreview.mockRejectedValueOnce(busy(retryAfterMs)).mockResolvedValue(preview);
    await expect(fetchLinkPreview("https://a.example")).rejects.toThrow();

    clock.mockReturnValue(now + waitMs - 1);
    await expect(fetchLinkPreview("https://a.example")).rejects.toThrow("preview failed");
    expect(fetchPreview).toHaveBeenCalledTimes(1);

    clock.mockReturnValue(now + waitMs);
    await expect(fetchLinkPreview("https://a.example")).resolves.toEqual(preview);
    await expect(fetchLinkPreview("https://a.example")).resolves.toEqual(preview);
    expect(fetchPreview).toHaveBeenCalledTimes(2);
  });

  it("keeps other refusals for five minutes, the rate limit's 429 included", async () => {
    const now = Date.now();
    const clock = jest.spyOn(Date, "now").mockReturnValue(now);
    const limited = new ApiRequestError(429, JSON.stringify({ detail: { code: "rate_limited", message: "x" } }), 60_000);
    fetchPreview.mockRejectedValueOnce(limited).mockResolvedValue(preview);
    await expect(fetchLinkPreview("https://a.example")).rejects.toThrow();
    clock.mockReturnValue(now + 5 * 60_000 - 1);
    await expect(fetchLinkPreview("https://a.example")).rejects.toThrow("preview failed");
    expect(fetchPreview).toHaveBeenCalledTimes(1);
  });
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
