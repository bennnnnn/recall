jest.mock("@/lib/config", () => ({
  getApiUrl: () => "http://test.local",
}));

jest.mock("@/lib/auth", () => ({
  getRefreshToken: jest.fn(),
  setTokenPair: jest.fn(),
}));

import { chatWebSocketUrl, checkHealth } from "@/lib/api/connectivity";

const mockFetch = jest.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

beforeEach(() => {
  mockFetch.mockReset();
});

describe("api connectivity", () => {
  it("chatWebSocketUrl converts http base to ws", () => {
    expect(chatWebSocketUrl("abc-123")).toBe("ws://test.local/ws/chats/abc-123");
  });

  it("checkHealth returns true when /health is ok", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true });
    await expect(checkHealth()).resolves.toBe(true);
    expect(mockFetch).toHaveBeenCalledWith("http://test.local/health");
  });

  it("checkHealth returns false on network error", async () => {
    mockFetch.mockRejectedValueOnce(new Error("offline"));
    await expect(checkHealth()).resolves.toBe(false);
  });

  it("checkHealth returns false when response is not ok", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 503 });
    await expect(checkHealth()).resolves.toBe(false);
  });
});
