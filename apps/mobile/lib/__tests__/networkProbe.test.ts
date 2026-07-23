const mockRefresh = jest.fn();
const mockCheckHealth = jest.fn();

jest.mock("@react-native-community/netinfo", () => ({
  __esModule: true,
  default: {
    refresh: (...args: unknown[]) => mockRefresh(...args),
  },
}));

jest.mock("@/lib/api/connectivity", () => ({
  checkHealth: (...args: unknown[]) => mockCheckHealth(...args),
}));

import { checkPublicReachability, resolveIsOffline } from "@/lib/networkProbe";

const mockFetch = jest.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

beforeEach(() => {
  mockRefresh.mockReset();
  mockCheckHealth.mockReset();
  mockFetch.mockReset();
});

describe("checkPublicReachability", () => {
  it("returns true on generate_204", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });
    await expect(checkPublicReachability()).resolves.toBe(true);
  });

  it("returns false when fetch fails", async () => {
    mockFetch.mockRejectedValueOnce(new Error("offline"));
    await expect(checkPublicReachability()).resolves.toBe(false);
  });
});

describe("resolveIsOffline", () => {
  it("is online when NetInfo reports connected", async () => {
    mockRefresh.mockResolvedValueOnce({ isConnected: true, isInternetReachable: false });
    await expect(resolveIsOffline()).resolves.toBe(false);
    expect(mockCheckHealth).not.toHaveBeenCalled();
  });

  it("is online when NetInfo is stale offline but API health succeeds", async () => {
    mockRefresh.mockResolvedValueOnce({ isConnected: false, isInternetReachable: false });
    mockCheckHealth.mockResolvedValueOnce(true);
    await expect(resolveIsOffline()).resolves.toBe(false);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("is online when NetInfo + API fail but public internet works", async () => {
    mockRefresh.mockResolvedValueOnce({ isConnected: false, isInternetReachable: false });
    mockCheckHealth.mockResolvedValueOnce(false);
    mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });
    await expect(resolveIsOffline()).resolves.toBe(false);
  });

  it("is offline only when NetInfo, API, and public probe all fail", async () => {
    mockRefresh.mockResolvedValueOnce({ isConnected: false, isInternetReachable: false });
    mockCheckHealth.mockResolvedValueOnce(false);
    mockFetch.mockRejectedValueOnce(new Error("offline"));
    await expect(resolveIsOffline()).resolves.toBe(true);
  });
});
