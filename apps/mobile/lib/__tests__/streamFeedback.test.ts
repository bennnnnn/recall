import { createStreamCueGate, playStreamCue } from "@/lib/chat/streamFeedback";
import { notifyWarning, selection, tap } from "@/lib/haptics";

jest.mock("@/lib/haptics", () => ({
  selection: jest.fn(),
  tap: jest.fn(),
  notifyWarning: jest.fn(),
}));

describe("stream feedback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("maps each cue to one haptic", () => {
    playStreamCue("activity");
    playStreamCue("complete");
    playStreamCue("stopped");
    playStreamCue("error");
    expect(selection).toHaveBeenCalledTimes(1);
    expect(tap).toHaveBeenCalledTimes(2);
    expect(notifyWarning).toHaveBeenCalledTimes(1);
  });

  it("ticks once for activity and does not complete after stop", () => {
    const gate = createStreamCueGate();
    gate.activity();
    gate.activity();
    gate.stopped();
    gate.complete();
    expect(selection).toHaveBeenCalledTimes(1);
    expect(tap).toHaveBeenCalledTimes(1);
  });
});
