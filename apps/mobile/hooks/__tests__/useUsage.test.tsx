import { act, renderHook } from "@testing-library/react-native";

import { useUsage } from "@/hooks/useUsage";
import type { Usage } from "@/lib/api";

let mockToken: string | null = "account-a";
let mockGeneration = 0;
const mockFetchUsage = jest.fn();
const mockGetCachedUsage = jest.fn();

jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => mockToken }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockGeneration }));
jest.mock("@/lib/cache/usageCache", () => ({
  fetchTodayUsage: (...args: unknown[]) => mockFetchUsage(...args),
  getCachedUsage: (...args: unknown[]) => mockGetCachedUsage(...args),
  invalidateUsageCache: jest.fn(),
}));
jest.mock("expo-router", () => {
  const { useEffect } = jest.requireActual<typeof import("react")>("react");
  return { useFocusEffect: (callback: () => void) => useEffect(callback, [callback]) };
});

function usage(used = 12000): Usage {
  return {
    date: new Date().toISOString().slice(0, 10),
    input_tokens: used,
    output_tokens: 0,
    used_tokens: used,
    daily_limit: 100000,
    remaining: 100000 - used,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => {
  jest.clearAllMocks();
  mockFetchUsage.mockReset();
  mockToken = "account-a";
  mockGeneration = 0;
  mockGetCachedUsage.mockReturnValue(undefined);
});

it("moves from indeterminate loading to retryable failure and then loaded data", async () => {
  const pending = deferred<Usage | null>();
  mockFetchUsage.mockReturnValueOnce(pending.promise);
  const { result } = await renderHook(useUsage);
  expect(result.current.usage).toBeNull();
  expect(result.current.loading).toBe(true);
  await act(async () => { pending.resolve(null); });
  expect(result.current.loading).toBe(false);
  expect(result.current.error).toBe(true);
  mockFetchUsage.mockResolvedValueOnce(usage());
  await act(async () => { await result.current.refresh({ force: true }); });
  expect(mockFetchUsage).toHaveBeenLastCalledWith("account-a", { force: true });
  expect(result.current.usage?.used_tokens).toBe(12000);
  expect(result.current.error).toBe(false);
});

it("immediately hides the previous account's usage and ignores its late response", async () => {
  const accountA = deferred<Usage | null>();
  const accountB = deferred<Usage | null>();
  mockGetCachedUsage.mockImplementation((token: string) => token === "account-a" ? usage(1000) : undefined);
  mockFetchUsage.mockReturnValueOnce(accountA.promise).mockReturnValueOnce(accountB.promise);
  const { result, rerender } = await renderHook(useUsage);
  expect(result.current.usage?.used_tokens).toBe(1000);
  mockToken = "account-b";
  mockGeneration += 1;
  await rerender();
  expect(result.current.usage).toBeNull();
  await act(async () => { accountA.resolve(usage(2000)); });
  expect(result.current.usage).toBeNull();
  await act(async () => { accountB.resolve(usage(3000)); });
  expect(result.current.usage?.used_tokens).toBe(3000);
});

it("does not fetch from a retained retry callback after leaving the screen", async () => {
  mockFetchUsage.mockResolvedValueOnce(usage());
  const { result, unmount } = await renderHook(useUsage);
  const retry = result.current.refresh;
  await unmount();
  await act(async () => { await retry({ force: true }); });
  expect(mockFetchUsage).toHaveBeenCalledTimes(1);
});

it("does not present yesterday's cached usage as today's limit", async () => {
  const pending = deferred<Usage | null>();
  mockGetCachedUsage.mockReturnValue({ ...usage(), date: "2000-01-01" });
  mockFetchUsage.mockReturnValueOnce(pending.promise);
  const { result } = await renderHook(useUsage);
  expect(result.current.usage).toBeNull();
  expect(mockFetchUsage).toHaveBeenCalledWith("account-a", { force: true });
  await act(async () => { pending.resolve(usage()); });
  expect(result.current.usage?.used_tokens).toBe(12000);
});
