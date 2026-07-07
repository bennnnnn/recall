jest.mock("@/lib/config", () => ({
  getApiUrl: () => "https://api.test",
}));

jest.mock("@/lib/deviceTimezone", () => ({
  getDeviceTimezone: () => "UTC",
}));

jest.mock("@/lib/api/client", () => ({
  refreshAccessToken: jest.fn(),
}));

import { isSseAbortError, parseSseChunk, streamChatMessageSse } from "@/lib/chatSse";
import { refreshAccessToken } from "@/lib/api/client";

describe("parseSseChunk", () => {
  it("parses complete SSE frames and keeps trailing partial buffer", () => {
    const { events, rest } = parseSseChunk(
      'data: {"type":"token","content":"hi"}\n\ndata: {"type":"stream_end"}\n\ndata: {"type":"tok',
    );

    expect(events).toEqual([
      { type: "token", content: "hi" },
      { type: "stream_end" },
    ]);
    expect(rest).toBe('data: {"type":"tok');
  });
});

describe("isSseAbortError", () => {
  it("detects AbortError from fetch cancellation", () => {
    expect(isSseAbortError(new DOMException("aborted", "AbortError"))).toBe(true);
    expect(isSseAbortError(new Error("network"))).toBe(false);
  });
});

describe("streamChatMessageSse 401 refresh-retry", () => {
  const refreshMock = refreshAccessToken as jest.MockedFunction<typeof refreshAccessToken>;
  const originalFetch = globalThis.fetch;

  const makeOkStream = (payload: string) =>
    ({
      ok: true,
      status: 200,
      body: {
        getReader: () => ({
          read: jest
            .fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(payload),
            })
            .mockResolvedValueOnce({ done: true, value: undefined }),
        }),
      },
    }) as unknown as Response;

  beforeEach(() => {
    refreshMock.mockReset();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("refreshes the access token and retries once on 401", async () => {
    refreshMock.mockResolvedValue("fresh-token");
    const events: unknown[] = [];
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: () => Promise.resolve("unauthorized"),
      } as Response)
      .mockResolvedValueOnce(makeOkStream('data: {"type":"done"}\n\n'));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await streamChatMessageSse({
      token: "stale-token",
      chatId: "chat-1",
      content: "hi",
      onEvent: (e) => events.push(e),
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer stale-token");
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe("Bearer fresh-token");
    expect(events).toEqual([{ type: "done" }]);
  });

  it("does not retry when refresh returns null", async () => {
    refreshMock.mockResolvedValue(null);
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: () => Promise.resolve("unauthorized"),
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await expect(
      streamChatMessageSse({
        token: "stale-token",
        chatId: "chat-1",
        content: "hi",
        onEvent: () => {},
      }),
    ).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not refresh on a non-401 failure", async () => {
    refreshMock.mockResolvedValue("fresh-token");
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve("server error"),
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await expect(
      streamChatMessageSse({
        token: "good-token",
        chatId: "chat-1",
        content: "hi",
        onEvent: () => {},
      }),
    ).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(refreshMock).not.toHaveBeenCalled();
  });
});
