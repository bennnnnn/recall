import { memoriesApi } from "@/lib/api/memories";
import { request } from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({ request: jest.fn() }));

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(request).mockResolvedValue(undefined);
});

it("sends the exact selected fact with reserved characters and Unicode", async () => {
  const fact = "I like a+b & coffee / tea? #1 = 🫖";
  await memoriesApi.deleteMemoryFact("token", "memory-id", 3, fact);
  const [path, token, init] = jest.mocked(request).mock.calls[0];
  const url = new URL(path, "https://recall.test");
  expect(url.pathname).toBe("/memories/memory-id/facts/3");
  expect(url.searchParams.get("fact_text")).toBe(fact);
  expect(token).toBe("token");
  expect(init).toEqual({ method: "DELETE" });
});

it("encodes incomplete native Unicode input without throwing before the request", async () => {
  await expect(memoriesApi.deleteMemoryFact("token", "memory-id", 0, "a\ud83d")).resolves.toBeUndefined();
  const [path] = jest.mocked(request).mock.calls[0];
  expect(new URL(path, "https://recall.test").searchParams.get("fact_text")).toBe("a\ufffd");
});

it("allows a maximum saved fact plus its server date stamp, counting Unicode code points", async () => {
  const fact = `As of 2026-09-04: ${"🫖".repeat(4000)}`;
  await memoriesApi.deleteMemoryFact("token", "memory-id", 0, fact);
  const [path] = jest.mocked(request).mock.calls[0];
  expect(new URL(path, "https://recall.test").searchParams.get("fact_text")).toBe(fact);
});

it("rejects an oversized selector without truncating it or sending a positional deletion", async () => {
  await expect(memoriesApi.deleteMemoryFact("token", "memory-id", 0, "a".repeat(4019))).rejects.toThrow();
  expect(request).not.toHaveBeenCalled();
});
