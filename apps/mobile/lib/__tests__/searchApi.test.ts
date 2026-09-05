import { discoverApi } from "@/lib/api/discover";
import { request } from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({ request: jest.fn() }));
beforeEach(() => { jest.clearAllMocks(); jest.mocked(request).mockResolvedValue({ results: [], total: 0 }); });

it("preserves literal search text, cancellation and pagination at the network boundary", async () => {
  const signal = new AbortController().signal;
  const query = "a+b &?# 💬";
  await discoverApi.search("token", query, 20, { signal }, 40);
  const [path, token, init] = jest.mocked(request).mock.calls[0];
  const url = new URL(path, "https://recall.test");
  expect(url.searchParams.get("q")).toBe(query);
  expect(url.searchParams.get("limit")).toBe("20");
  expect(url.searchParams.get("offset")).toBe("40");
  expect(token).toBe("token");
  expect(init).toEqual({ signal });
});

it("encodes incomplete native Unicode input without throwing before the request", async () => {
  await expect(discoverApi.search("token", "a\ud83d")).resolves.toEqual({ results: [], total: 0 });
  const [path] = jest.mocked(request).mock.calls[0];
  expect(new URL(path, "https://recall.test").searchParams.get("q")).toBe("a\ufffd");
});
