jest.mock("@/lib/config", () => ({
  getApiUrl: () => "https://api.test",
}));

import { isSseAbortError, parseSseChunk } from "@/lib/chatSse";

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
