jest.mock("@/lib/config", () => ({
  getApiUrl: () => "http://test.local",
}));

const mockGetRefreshToken = jest.fn();
const mockSetTokenPair = jest.fn();

jest.mock("@/lib/auth", () => ({
  getRefreshToken: (...args: unknown[]) => mockGetRefreshToken(...args),
  setTokenPair: (...args: unknown[]) => mockSetTokenPair(...args),
}));

import {
  apiUrl,
  fetchWithTimeout,
  request,
  setTokenRefreshHandler,
  setUnauthorizedHandler,
} from "@/lib/api/client";

const mockFetch = jest.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

beforeEach(() => {
  mockFetch.mockReset();
  mockGetRefreshToken.mockReset();
  mockSetTokenPair.mockReset();
  setUnauthorizedHandler(null);
  setTokenRefreshHandler(null);
});

describe("api client", () => {
  it("apiUrl prefixes paths with configured base", () => {
    expect(apiUrl("/chats")).toBe("http://test.local/chats");
  });

  it("request returns JSON on success", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ id: "chat-1" }),
    });

    const data = await request<{ id: string }>("/chats/1", "access-token");
    expect(data).toEqual({ id: "chat-1" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://test.local/chats/1",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer access-token",
        }),
      }),
    );
  });

  it("request refreshes on 401 and retries once", async () => {
    mockGetRefreshToken.mockResolvedValue("refresh-token");
    mockSetTokenPair.mockResolvedValue(undefined);

    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => "expired",
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          access_token: "new-access",
          refresh_token: "new-refresh",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ ok: true }),
      });

    const onRefresh = jest.fn();
    setTokenRefreshHandler(onRefresh);

    const data = await request<{ ok: boolean }>("/users/me", "stale-token");
    expect(data).toEqual({ ok: true });
    expect(mockFetch).toHaveBeenCalledTimes(3);
    expect(mockSetTokenPair).toHaveBeenCalledWith("new-access", "new-refresh");
    expect(onRefresh).toHaveBeenCalledWith("new-access");
    expect(mockFetch.mock.calls[2][1]?.headers).toMatchObject({
      Authorization: "Bearer new-access",
    });
  });

  it("request calls onUnauthorized when refresh fails", async () => {
    mockGetRefreshToken.mockResolvedValue("refresh-token");

    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => "expired",
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => "invalid refresh",
      });

    const onUnauthorized = jest.fn();
    setUnauthorizedHandler(onUnauthorized);

    await expect(request("/users/me", "stale-token")).rejects.toThrow("expired");
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("single-flights concurrent refresh attempts", async () => {
    mockGetRefreshToken.mockResolvedValue("refresh-token");
    mockSetTokenPair.mockResolvedValue(undefined);

    let resolveRefresh: (value: Response) => void;
    const refreshPromise = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });

    mockFetch
      .mockResolvedValueOnce({ ok: false, status: 401, text: async () => "" })
      .mockResolvedValueOnce({ ok: false, status: 401, text: async () => "" })
      .mockImplementationOnce(() => refreshPromise)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ a: 1 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ b: 2 }),
      });

    const p1 = request("/a", "t1");
    const p2 = request("/b", "t2");

    resolveRefresh!({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: "shared-access",
        refresh_token: "shared-refresh",
      }),
    } as Response);

    await expect(Promise.all([p1, p2])).resolves.toEqual([{ a: 1 }, { b: 2 }]);
    const refreshCalls = mockFetch.mock.calls.filter(
      (call) => call[0] === "http://test.local/auth/refresh",
    );
    expect(refreshCalls).toHaveLength(1);
  });

  it("fetchWithTimeout surfaces a friendly message on abort", async () => {
    const abortError = new Error("Aborted");
    abortError.name = "AbortError";
    mockFetch.mockRejectedValueOnce(abortError);

    await expect(
      fetchWithTimeout("http://test.local/auth/login", { method: "POST" }),
    ).rejects.toThrow("Could not reach the Recall server");
  });
});
