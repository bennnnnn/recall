import { isSseAbortError, parseSseChunk, shouldAbortPriorSse, streamChatMessageSse } from "@/lib/chatSse";
import { notifyUnauthorized, requestSse } from "@/lib/api/client";

jest.mock("@/lib/config", () => ({
  getApiUrl: () => "https://api.test",
}));

jest.mock("@/lib/deviceTimezone", () => ({
  getDeviceTimezone: () => "UTC",
}));

// Mock requestSse (the lib/api boundary helper) so the test verifies chatSse
// routes through it and handles the Response. The 401→refresh→retry behaviour
// lives in requestRaw (tested separately), not in chatSse anymore.
jest.mock("@/lib/api/client", () => ({
  requestSse: jest.fn(),
  notifyUnauthorized: jest.fn(),
  refreshAccessToken: jest.fn(),
}));

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

  it("recognizes React Native cancellation errors without requiring DOMException", () => {
    const error = new Error("cancelled");
    error.name = "AbortError";
    expect(isSseAbortError(error)).toBe(true);
  });
});

describe("shouldAbortPriorSse", () => {
  it("aborts only when replacing a stream in the same chat", () => {
    expect(shouldAbortPriorSse("chat-a", "chat-a")).toBe(true);
    expect(shouldAbortPriorSse("chat-a", "chat-b")).toBe(false);
    expect(shouldAbortPriorSse(null, "chat-b")).toBe(false);
  });
});

const makeOkStream = (payload: string) =>
  ({
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        releaseLock: jest.fn(),
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

describe("streamChatMessageSse routes through lib/api requestSse", () => {
  const requestSseMock = requestSse as jest.MockedFunction<typeof requestSse>;
  const unauthorizedMock = notifyUnauthorized as jest.MockedFunction<typeof notifyUnauthorized>;

  beforeEach(() => {
    requestSseMock.mockReset();
    unauthorizedMock.mockReset();
  });

  it("calls requestSse with the send path, token, and body", async () => {
    requestSseMock.mockResolvedValueOnce(makeOkStream('data: {"type":"done"}\n\n'));
    const events: unknown[] = [];
    await streamChatMessageSse({
      token: "tok",
      chatId: "chat-1",
      content: "hi",
      onEvent: (e) => events.push(e),
    });

    expect(requestSseMock).toHaveBeenCalledTimes(1);
    const [path, token, body] = requestSseMock.mock.calls[0];
    expect(path).toBe("/chats/chat-1/messages/stream");
    expect(token).toBe("tok");
    expect(body).toMatchObject({ content: "hi", model: null });
    expect(events).toEqual([{ type: "done" }]);
  });

  it("throws and calls notifyUnauthorized when response is 401", async () => {
    requestSseMock.mockResolvedValueOnce({
      ok: false,
      status: 401,
      text: () => Promise.resolve("unauthorized"),
    } as Response);

    await expect(
      streamChatMessageSse({
        token: "tok",
        chatId: "chat-1",
        content: "hi",
        onEvent: () => {},
      }),
    ).rejects.toThrow();
    expect(unauthorizedMock).toHaveBeenCalledTimes(1);
  });

  it("throws on a non-401 failure without calling notifyUnauthorized", async () => {
    requestSseMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: () => Promise.resolve("server error"),
    } as Response);

    await expect(
      streamChatMessageSse({
        token: "tok",
        chatId: "chat-1",
        content: "hi",
        onEvent: () => {},
      }),
    ).rejects.toThrow();
    expect(unauthorizedMock).not.toHaveBeenCalled();
  });

  it("throws when the response has no body", async () => {
    requestSseMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: null,
    } as unknown as Response);

    await expect(
      streamChatMessageSse({
        token: "tok",
        chatId: "chat-1",
        content: "hi",
        onEvent: () => {},
      }),
    ).rejects.toThrow();
  });

  it("rejects a truncated response after tokens instead of leaving the composer busy", async () => {
    requestSseMock.mockResolvedValueOnce(makeOkStream(
      'data: {"type":"start"}\n\ndata: {"type":"token","content":"partial"}\n\n',
    ));
    const onEvent = jest.fn();
    await expect(streamChatMessageSse({
      token: "tok", chatId: "chat-1", content: "hi", onEvent,
    })).rejects.toThrow("before completion");
    expect(onEvent).toHaveBeenCalledWith({ type: "token", content: "partial" });
  });

  it("requires saved completion even after stream_end", async () => {
    requestSseMock.mockResolvedValueOnce(makeOkStream('data: {"type":"stream_end"}\n\n'));
    await expect(streamChatMessageSse({
      token: "tok", chatId: "chat-1", content: "hi", onEvent: jest.fn(),
    })).rejects.toThrow("before completion");
  });

  it("accepts error completion and CRLF framed streams", async () => {
    requestSseMock.mockResolvedValueOnce(makeOkStream(
      'data: {"type":"start"}\r\n\r\ndata: {"type":"error","message":"busy"}\r\n\r\n',
    ));
    const onEvent = jest.fn();
    await streamChatMessageSse({ token: "tok", chatId: "chat-1", content: "hi", onEvent });
    expect(onEvent.mock.calls.map(([event]) => event.type)).toEqual(["start", "error"]);
  });
});
