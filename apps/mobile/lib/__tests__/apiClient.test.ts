/**
 * lib/api/client.ts is the single network boundary for the app — every
 * request's auth header, 401-refresh-retry flow, and single-flight refresh
 * lives here. It was previously untested (the real module transitively pulls
 * in expo-constants/expo-secure-store, which this repo's ts-jest setup can't
 * transform), so @/lib/config and @/lib/auth are mocked to isolate the pure
 * request logic from those native modules.
 */

jest.mock("@/lib/config", () => ({
  getApiUrl: () => "https://api.test",
}));

const mockGetRefreshToken = jest.fn<Promise<string | null>, []>();
const mockSetTokenPair = jest.fn<Promise<void>, [string, string]>();

jest.mock("@/lib/auth", () => ({
  getRefreshToken: (...args: unknown[]) => mockGetRefreshToken(...(args as [])),
  setTokenPair: (...args: [string, string]) => mockSetTokenPair(...args),
}));

import {
  apiUrl,
  fetchExportText,
  logoutSession,
  request,
  setTokenRefreshHandler,
  setUnauthorizedHandler,
} from "@/lib/api/client";

function jsonResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

function textErrorResponse(status: number, body: string): Response {
  return {
    status,
    ok: false,
    json: async () => {
      throw new Error("not json");
    },
    text: async () => body,
  } as unknown as Response;
}

describe("lib/api/client", () => {
  beforeEach(() => {
    mockGetRefreshToken.mockReset();
    mockSetTokenPair.mockReset();
    globalThis.fetch = jest.fn();
  });

  afterEach(() => {
    setUnauthorizedHandler(null);
    setTokenRefreshHandler(null);
  });

  describe("apiUrl", () => {
    it("prefixes the path with the configured API base URL", () => {
      expect(apiUrl("/chats")).toBe("https://api.test/chats");
    });
  });

  describe("request", () => {
    it("attaches the bearer token and returns parsed JSON on success", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

      const result = await request<{ ok: boolean }>("/chats", "token-123");

      expect(result).toEqual({ ok: true });
      const [url, init] = fetchMock.mock.calls[0];
      expect(url).toBe("https://api.test/chats");
      expect(init.headers.Authorization).toBe("Bearer token-123");
    });

    it("returns undefined for a 204 response without parsing a body", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      fetchMock.mockResolvedValueOnce({ status: 204, ok: true } as Response);

      const result = await request("/chats/1", "token-123");

      expect(result).toBeUndefined();
    });

    it("throws with the response body text on a non-401 error", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      fetchMock.mockResolvedValueOnce(textErrorResponse(500, "Internal error"));

      await expect(request("/chats", "token-123")).rejects.toThrow("Internal error");
    });

    it("refreshes the token once and retries on 401, succeeding with the new token", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      mockGetRefreshToken.mockResolvedValue("refresh-abc");
      fetchMock
        .mockResolvedValueOnce(textErrorResponse(401, "expired"))
        .mockResolvedValueOnce(
          jsonResponse(200, { access_token: "new-token", refresh_token: "refresh-xyz" }),
        )
        .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

      const result = await request<{ ok: boolean }>("/chats", "stale-token");

      expect(result).toEqual({ ok: true });
      expect(mockSetTokenPair).toHaveBeenCalledWith("new-token", "refresh-xyz");

      // First call: the original 401. Second: POST /auth/refresh. Third: retry with new token.
      expect(fetchMock).toHaveBeenCalledTimes(3);
      const refreshCall = fetchMock.mock.calls[1];
      expect(refreshCall[0]).toBe("https://api.test/auth/refresh");
      const retryCall = fetchMock.mock.calls[2];
      expect(retryCall[1].headers.Authorization).toBe("Bearer new-token");
    });

    it("calls the unauthorized handler and throws when there's no refresh token", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      mockGetRefreshToken.mockResolvedValue(null);
      fetchMock.mockResolvedValueOnce(textErrorResponse(401, "expired"));
      const onUnauthorized = jest.fn();
      setUnauthorizedHandler(onUnauthorized);

      await expect(request("/chats", "stale-token")).rejects.toThrow("expired");
      expect(onUnauthorized).toHaveBeenCalledTimes(1);
      expect(mockSetTokenPair).not.toHaveBeenCalled();
    });

    it("does not permanently wedge refresh after a missing-refresh-token 401", async () => {
      // Regression: refreshAccessToken used to return early (no refresh
      // token) *before* its try/finally, so `refreshInFlight` was never
      // cleared — every subsequent request(), for the rest of the app
      // session, would short-circuit to that same stale resolved-to-null
      // promise, even once a real refresh token became available.
      const fetchMock = globalThis.fetch as jest.Mock;

      mockGetRefreshToken.mockResolvedValueOnce(null);
      fetchMock.mockResolvedValueOnce(textErrorResponse(401, "expired"));
      await expect(request("/chats", "stale-token")).rejects.toThrow("expired");

      mockGetRefreshToken.mockResolvedValueOnce("refresh-abc");
      fetchMock
        .mockResolvedValueOnce(textErrorResponse(401, "expired"))
        .mockResolvedValueOnce(
          jsonResponse(200, { access_token: "new-token", refresh_token: "refresh-xyz" }),
        )
        .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

      const result = await request<{ ok: boolean }>("/chats", "stale-token");

      expect(result).toEqual({ ok: true });
      expect(mockGetRefreshToken).toHaveBeenCalledTimes(2);
    });

    it("calls the unauthorized handler when the refresh request itself fails", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      mockGetRefreshToken.mockResolvedValue("refresh-abc");
      fetchMock
        .mockResolvedValueOnce(textErrorResponse(401, "expired"))
        .mockResolvedValueOnce(textErrorResponse(400, "invalid refresh token"));
      const onUnauthorized = jest.fn();
      setUnauthorizedHandler(onUnauthorized);

      await expect(request("/chats", "stale-token")).rejects.toThrow("expired");
      expect(onUnauthorized).toHaveBeenCalledTimes(1);
    });

    it("single-flights concurrent 401s into exactly one refresh call", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      mockGetRefreshToken.mockResolvedValue("refresh-abc");
      fetchMock.mockImplementation((url: string) => {
        if (url === "https://api.test/auth/refresh") {
          return Promise.resolve(
            jsonResponse(200, { access_token: "new-token", refresh_token: "refresh-xyz" }),
          );
        }
        return Promise.resolve(jsonResponse(200, { ok: true }));
      });
      // Only the very first two application calls should see a 401; simulate
      // that by having the mock's initial two resolutions be 401s via
      // mockImplementationOnce stacked before the general implementation.
      fetchMock
        .mockImplementationOnce(() => Promise.resolve(textErrorResponse(401, "expired")))
        .mockImplementationOnce(() => Promise.resolve(textErrorResponse(401, "expired")));

      const [first, second] = await Promise.all([
        request<{ ok: boolean }>("/chats/1", "stale-token"),
        request<{ ok: boolean }>("/chats/2", "stale-token"),
      ]);

      expect(first).toEqual({ ok: true });
      expect(second).toEqual({ ok: true });
      const refreshCalls = fetchMock.mock.calls.filter(
        ([url]) => url === "https://api.test/auth/refresh",
      );
      expect(refreshCalls).toHaveLength(1);
      expect(mockGetRefreshToken).toHaveBeenCalledTimes(1);
    });
  });

  describe("logoutSession", () => {
    it("is best-effort and does not throw when the request fails", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      fetchMock.mockRejectedValueOnce(new Error("network down"));

      await expect(logoutSession("token-123", "refresh-abc")).resolves.toBeUndefined();
    });

    it("sends the bearer token and refresh token to /auth/logout", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      fetchMock.mockResolvedValueOnce(jsonResponse(200, {}));

      await logoutSession("token-123", "refresh-abc");

      const [url, init] = fetchMock.mock.calls[0];
      expect(url).toBe("https://api.test/auth/logout");
      expect(init.headers.Authorization).toBe("Bearer token-123");
      expect(JSON.parse(init.body)).toEqual({ refresh_token: "refresh-abc" });
    });
  });

  describe("fetchExportText", () => {
    it("returns the raw response text on success", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      fetchMock.mockResolvedValueOnce({
        status: 200,
        ok: true,
        text: async () => "exported-data",
      } as Response);

      const text = await fetchExportText("token-123");

      expect(text).toBe("exported-data");
    });

    it("refreshes and retries once on 401", async () => {
      const fetchMock = globalThis.fetch as jest.Mock;
      mockGetRefreshToken.mockResolvedValue("refresh-abc");
      fetchMock
        .mockResolvedValueOnce(textErrorResponse(401, "expired"))
        .mockResolvedValueOnce(
          jsonResponse(200, { access_token: "new-token", refresh_token: "refresh-xyz" }),
        )
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          text: async () => "exported-data",
        } as Response);

      const text = await fetchExportText("stale-token");

      expect(text).toBe("exported-data");
      const retryCall = fetchMock.mock.calls[2];
      expect(retryCall[1].headers.Authorization).toBe("Bearer new-token");
    });
  });
});
