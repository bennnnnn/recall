import {
  LIVE_TALK_MAX_RECORDING_MS,
  LIVE_TALK_NO_SPEECH_MS,
  liveTalkCanTakeFloor,
  liveTalkErrorGate,
  liveTalkGate,
  liveTalkOrbAction,
  liveTalkSilenceDecision,
  type LiveTalkStatus,
} from "@/lib/liveTalkLogic";

const proReady: LiveTalkStatus = {
  enabled: true,
  entitled: true,
  remaining: 12,
  limit: 30,
};

describe("liveTalkGate", () => {
  it("blocks offline before status", () => {
    expect(liveTalkGate(proReady, true)).toBe("offline");
  });

  it("opens upgrade when free (limit 0)", () => {
    expect(
      liveTalkGate({ enabled: true, entitled: false, remaining: 0, limit: 0 }, false),
    ).toBe("upgrade");
  });

  it("opens limit when Pro is exhausted", () => {
    expect(
      liveTalkGate({ enabled: true, entitled: true, remaining: 0, limit: 30 }, false),
    ).toBe("limit");
  });

  it("allows a remaining Pro turn", () => {
    expect(liveTalkGate(proReady, false)).toBe("ok");
  });
});

describe("liveTalkErrorGate", () => {
  it("maps 403 to upgrade and 429 to limit", () => {
    expect(liveTalkErrorGate({ status: 403 })).toBe("upgrade");
    expect(liveTalkErrorGate({ status: 429 })).toBe("limit");
  });
});

describe("liveTalkOrbAction", () => {
  it("pauses speech, resumes, and cancels thinking", () => {
    expect(liveTalkOrbAction("speaking")).toBe("pause");
    expect(liveTalkOrbAction("paused")).toBe("resume");
    expect(liveTalkOrbAction("thinking")).toBe("cancelThink");
    expect(liveTalkOrbAction("recording")).toBe("finishListen");
    expect(liveTalkOrbAction("idle")).toBe("begin");
  });

  it("offers Speak only while audio is playing or paused", () => {
    expect(liveTalkCanTakeFloor("speaking")).toBe(true);
    expect(liveTalkCanTakeFloor("paused")).toBe(true);
    expect(liveTalkCanTakeFloor("recording")).toBe(false);
    expect(liveTalkCanTakeFloor("thinking")).toBe(false);
  });
});

describe("liveTalkSilenceDecision", () => {
  it("stops after speech then a short pause", () => {
    let state = liveTalkSilenceDecision({
      meter: 0.6,
      now: 1000,
      recordingStartedAt: 0,
      heardSpeech: false,
      silenceStartedAt: null,
    });
    expect(state.heardSpeech).toBe(true);
    state = liveTalkSilenceDecision({
      meter: 0.12,
      now: 1400,
      recordingStartedAt: 0,
      heardSpeech: true,
      silenceStartedAt: 1400,
    });
    expect(state.shouldStop).toBe(false);
    state = liveTalkSilenceDecision({
      meter: 0.12,
      now: 2000,
      recordingStartedAt: 0,
      heardSpeech: true,
      silenceStartedAt: 1400,
    });
    expect(state.shouldStop).toBe(true);
  });

  it("stops at the max duration even without speech", () => {
    const state = liveTalkSilenceDecision({
      meter: 0.1,
      now: LIVE_TALK_MAX_RECORDING_MS,
      recordingStartedAt: 0,
      heardSpeech: false,
      silenceStartedAt: null,
    });
    expect(state.shouldStop).toBe(true);
  });

  it("stops if the meter never crosses speech level", () => {
    const state = liveTalkSilenceDecision({
      meter: 0.1,
      now: LIVE_TALK_NO_SPEECH_MS,
      recordingStartedAt: 0,
      heardSpeech: false,
      silenceStartedAt: null,
    });
    expect(state.shouldStop).toBe(true);
  });
});
