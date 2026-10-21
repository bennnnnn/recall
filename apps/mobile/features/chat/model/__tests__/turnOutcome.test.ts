import { reportChatTurnOutcome } from "@/features/chat/model/latencyReporter";
import { applyChatEvent, type ChatEventContext } from "@/features/chat/model/chatEvents";
import {
  beginTurnOutcome,
  completionFromDone,
  noteTurnActivity,
  noteTurnSendReady,
  noteTurnToken,
  reportTurnOutcome,
  sendReadyBucket,
  turnOutcomeProperties,
} from "@/features/chat/model/turnOutcome";

jest.mock("@/features/chat/model/latencyReporter", () => ({
  reportChatTurnOutcome: jest.fn(async () => undefined),
}));
// chatEvents announces a finished reply; nothing here reaches that.
jest.mock("react-native", () => ({ AccessibilityInfo: { announceForAccessibility: jest.fn() } }));

const report = reportChatTurnOutcome as jest.Mock;
const settle = () => new Promise<void>((done) => setImmediate(() => done()));

describe("chat_turn_outcome (O10.1)", () => {
  beforeEach(async () => {
    // Close a turn an earlier case left open.
    reportTurnOutcome("complete");
    await settle();
    report.mockClear();
  });

  it("names the first tool the turn showed and a clean finish", async () => {
    beginTurnOutcome();
    noteTurnActivity("composing");
    noteTurnActivity("searching");
    noteTurnActivity("calculating");
    reportTurnOutcome(completionFromDone(undefined));
    await settle();
    expect(report).toHaveBeenCalledWith({
      completion: "complete", error_code: "none", tool: "searching", send_ready_bucket: "none",
    });
  });

  it("reports a turn once, whatever frames follow", async () => {
    beginTurnOutcome();
    reportTurnOutcome("stopped");
    reportTurnOutcome(completionFromDone("user_stop"));
    reportTurnOutcome("error", "busy");
    await settle();
    expect(report).toHaveBeenCalledTimes(1);
    expect(report).toHaveBeenCalledWith({
      completion: "stopped", error_code: "none", tool: "none", send_ready_bucket: "none",
    });
  });

  it("keeps only the server's own error codes; anything else is other", () => {
    beginTurnOutcome();
    expect(turnOutcomeProperties("error", "model_unavailable").error_code).toBe("model_unavailable");
    expect(turnOutcomeProperties("error", "That model isn't responding").error_code).toBe("other");
    expect(turnOutcomeProperties("error").error_code).toBe("other");
    expect(turnOutcomeProperties("complete", "busy").error_code).toBe("none");
  });

  it("reads the done frame's completion", () => {
    expect(completionFromDone("user_stop")).toBe("stopped");
    expect(completionFromDone("interrupted")).toBe("interrupted");
    expect(completionFromDone("complete")).toBe("complete");
  });

  it("never reports a turn that did not start", async () => {
    reportTurnOutcome("error", "busy");
    await settle();
    expect(report).not.toHaveBeenCalled();
  });

  it.each([
    [null, "none"],
    [0, "lt100"],
    [99, "lt100"],
    [100, "100_249"],
    [250, "250_499"],
    [500, "500_999"],
    [1_000, "1000_1999"],
    [2_000, "2000_plus"],
  ])("buckets last token -> Send ready of %p ms as %s", (elapsedMs, bucket) => {
    expect(sendReadyBucket(elapsedMs)).toBe(bucket);
  });

  it("measures last token -> Send ready from the chat events, once per turn", async () => {
    const now = jest.spyOn(Date, "now").mockReturnValue(1_000);
    const ctx = {
      t: (key: string) => key,
      setFinalizing: jest.fn(),
      setMessages: jest.fn(),
      updateStreamingDraft: jest.fn(),
      streamingRef: { current: true },
      streamCueRef: { current: { activity: jest.fn() } },
      pendingSendRef: { current: null },
      assistantBufferRef: { current: "" },
      streamingDraftRef: { current: null },
    } as unknown as ChatEventContext;
    beginTurnOutcome();
    applyChatEvent({ type: "token", content: "Hel" }, ctx);
    now.mockReturnValue(1_050);
    applyChatEvent({ type: "token", content: "lo" }, ctx);
    now.mockReturnValue(1_350);
    applyChatEvent({ type: "stream_end" }, ctx);
    now.mockReturnValue(9_000);
    noteTurnSendReady();
    expect(turnOutcomeProperties("complete").send_ready_bucket).toBe("250_499");
    now.mockRestore();
  });

  it("leaves Send ready unmeasured for a turn with no stream_end, or none before it", () => {
    beginTurnOutcome();
    noteTurnSendReady();
    expect(turnOutcomeProperties("error").send_ready_bucket).toBe("none");
    noteTurnToken();
    expect(turnOutcomeProperties("stopped").send_ready_bucket).toBe("none");
    // A new turn starts clean.
    noteTurnSendReady();
    beginTurnOutcome();
    expect(turnOutcomeProperties("complete").send_ready_bucket).toBe("none");
  });
});
