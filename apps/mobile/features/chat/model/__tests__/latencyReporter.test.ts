import { reportChatTtft, reportChatTurnOutcome } from "@/features/chat/model/latencyReporter";
import { trackProductEvent } from "@/lib/productAnalytics";

jest.mock("@/lib/productAnalytics", () => ({ trackProductEvent: jest.fn() }));

const track = trackProductEvent as jest.Mock;

describe("chat event reporter", () => {
  beforeEach(() => track.mockClear());

  it("queues one chat_turn_outcome holding only its enumerated properties and its rate", async () => {
    await reportChatTurnOutcome({ completion: "error", error_code: "busy", tool: "searching" });
    expect(track).toHaveBeenCalledTimes(1);
    expect(track).toHaveBeenCalledWith("chat_turn_outcome", {
      completion: "error",
      error_code: "busy",
      tool: "searching",
      sample_rate: "0.2",
    });
  });

  it("queues one bucketed chat_ttft with its rate", async () => {
    await reportChatTtft({ latencyBucket: "500_999", transport: "sse", hasAttachment: true });
    expect(track).toHaveBeenCalledWith("chat_ttft", {
      latency_bucket: "500_999",
      transport: "sse",
      has_attachment: "yes",
      sample_rate: "0.2",
    });
  });
});
