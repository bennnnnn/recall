import { parseChatWsPayload } from "@/lib/chatSocketReduce";
import { reportChatTtft } from "@/lib/chatLatencyReporter";
import {
  chatTtftBucket,
  clearPendingChatTtft,
  markChatFirstToken,
  markChatTtftStart,
  markChatTtftTransport,
} from "@/lib/chatLatency";

jest.mock("@/lib/chatLatencyReporter", () => ({
  reportChatTtft: jest.fn(async () => undefined),
}));

const startedAt = "2026-01-01T00:00:00.000Z";
const devHolder = globalThis as unknown as { __DEV__?: boolean };
const originalDev = devHolder.__DEV__;

async function flushTtftReport(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe("chatTtftBucket", () => {
  it.each([
    [0, "lt500"],
    [499, "lt500"],
    [500, "500_999"],
    [999, "500_999"],
    [1_000, "1000_1999"],
    [1_999, "1000_1999"],
    [2_000, "2000_3999"],
    [3_999, "2000_3999"],
    [4_000, "4000_5999"],
    [5_999, "4000_5999"],
    [6_000, "6000_plus"],
  ])("buckets %sms as %s", (elapsedMs, expected) => {
    expect(chatTtftBucket(elapsedMs as number)).toBe(expected);
  });
});

describe("pending chat TTFT samples", () => {
  beforeEach(() => {
    devHolder.__DEV__ = false;
    clearPendingChatTtft();
    jest.mocked(reportChatTtft).mockClear();
    jest.spyOn(Date, "now").mockReturnValue(Date.parse(startedAt) + 750);
  });

  afterEach(() => {
    clearPendingChatTtft();
    jest.restoreAllMocks();
    if (originalDev === undefined) {
      delete devHolder.__DEV__;
    } else {
      devHolder.__DEV__ = originalDev;
    }
  });

  it("reports the originating turn after its token is accepted", async () => {
    markChatTtftStart("turn-b", startedAt, true);
    markChatTtftTransport("turn-b", "sse");
    markChatFirstToken("turn-b", "token");
    await flushTtftReport();
    expect(reportChatTtft).toHaveBeenCalledTimes(1);
    expect(reportChatTtft).toHaveBeenCalledWith({
      latencyBucket: "500_999",
      transport: "sse",
      hasAttachment: true,
    });
  });

  it("does not let leftover chat A consume chat B's sample", async () => {
    markChatTtftStart("turn-a", startedAt, false);
    markChatTtftStart("turn-b", startedAt, true);
    markChatTtftTransport("turn-a", "sse");
    parseChatWsPayload(JSON.stringify({ type: "token", content: "hi" }));
    markChatFirstToken("turn-a", "token");
    await flushTtftReport();
    expect(reportChatTtft).not.toHaveBeenCalled();

    markChatFirstToken("turn-b", "token");
    await flushTtftReport();
    expect(reportChatTtft).toHaveBeenCalledTimes(1);
    expect(reportChatTtft).toHaveBeenCalledWith({
      latencyBucket: "500_999",
      transport: "ws",
      hasAttachment: true,
    });
  });

  it("does not let a later regenerate consume a cancelled send's sample", async () => {
    markChatTtftStart("turn-a", startedAt, false);
    clearPendingChatTtft("turn-a");
    markChatFirstToken("turn-a", "token");
    markChatFirstToken(undefined, "token");
    await flushTtftReport();
    expect(reportChatTtft).not.toHaveBeenCalled();
  });

  it("does not clear a newer send when discarding an older turn", async () => {
    markChatTtftStart("turn-a", startedAt, false);
    markChatTtftStart("turn-b", startedAt, true);
    clearPendingChatTtft("turn-a");
    markChatFirstToken("turn-b", "token");
    await flushTtftReport();
    expect(reportChatTtft).toHaveBeenCalledTimes(1);
  });
});
