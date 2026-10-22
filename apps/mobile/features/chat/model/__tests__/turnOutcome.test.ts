import { reportChatTurnOutcome } from "@/features/chat/model/latencyReporter";
import {
  beginTurnOutcome,
  completionFromDone,
  noteTurnActivity,
  reportTurnOutcome,
  turnOutcomeProperties,
} from "@/features/chat/model/turnOutcome";

jest.mock("@/features/chat/model/latencyReporter", () => ({
  reportChatTurnOutcome: jest.fn(async () => undefined),
}));

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
    expect(report).toHaveBeenCalledWith({ completion: "complete", error_code: "none", tool: "searching" });
  });

  it("does not count the photo found above a finished reply as the turn's tool", async () => {
    beginTurnOutcome();
    noteTurnActivity("composing");
    noteTurnActivity("answer_photo");
    noteTurnActivity("finishing");
    reportTurnOutcome(completionFromDone(undefined));
    await settle();
    expect(report).toHaveBeenCalledWith({ completion: "complete", error_code: "none", tool: "none" });
  });

  it("reports a turn once, whatever frames follow", async () => {
    beginTurnOutcome();
    reportTurnOutcome("stopped");
    reportTurnOutcome(completionFromDone("user_stop"));
    reportTurnOutcome("error", "busy");
    await settle();
    expect(report).toHaveBeenCalledTimes(1);
    expect(report).toHaveBeenCalledWith({ completion: "stopped", error_code: "none", tool: "none" });
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
});
