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
  requestRaw,
  requestSse,
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

  it("requestRaw returns the raw Response on success and adds Authorization", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: "stream",
    } as unknown as Response);

    const res = await requestRaw("/link-preview?url=x", "access-token");
    expect(res.ok).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://test.local/link-preview?url=x",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer access-token",
        }),
      }),
    );
  });

  it("requestRaw omits Authorization when token is null", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, status: 200 } as unknown as Response);
    await requestRaw("/link-preview?url=x", null);
    expect(mockFetch.mock.calls[0][1]?.headers).not.toHaveProperty("Authorization");
  });

  it("requestRaw refreshes on 401 and retries once with the fresh token", async () => {
    mockGetRefreshToken.mockResolvedValue("refresh-token");
    mockSetTokenPair.mockResolvedValue(undefined);

    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => "expired",
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          access_token: "new-access",
          refresh_token: "new-refresh",
        }),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        body: "stream",
      } as unknown as Response);

    const res = await requestRaw("/link-preview?url=x", "stale-token");
    expect(res.ok).toBe(true);
    expect(mockFetch).toHaveBeenCalledTimes(3);
    // Third call (the retry) uses the refreshed token.
    expect(mockFetch.mock.calls[2][1]?.headers).toMatchObject({
      Authorization: "Bearer new-access",
    });
  });

  it("requestRaw calls onUnauthorized and returns the 401 response when refresh fails", async () => {
    mockGetRefreshToken.mockResolvedValue("refresh-token");

    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => "expired",
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => "invalid refresh",
      } as unknown as Response);

    const onUnauthorized = jest.fn();
    setUnauthorizedHandler(onUnauthorized);

    const res = await requestRaw("/link-preview?url=x", "stale-token");
    expect(res.ok).toBe(false);
    expect(res.status).toBe(401);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("requestSse sets SSE headers (Accept + Content-Type) and POSTs the body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: "stream",
    } as unknown as Response);

    await requestSse("/chats/c1/messages/stream", "tok", { content: "hi" });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, init] = mockFetch.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      Authorization: "Bearer tok",
    });
    expect(init?.body).toBe(JSON.stringify({ content: "hi" }));
  });
});
