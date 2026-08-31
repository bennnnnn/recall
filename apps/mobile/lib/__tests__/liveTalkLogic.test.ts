import {
  LIVE_TALK_MAX_RECORDING_MS,
  LIVE_TALK_NO_SPEECH_MS,
  liveTalkAbortRefundNeeded,
  liveTalkCanTakeFloor,
  liveTalkErrorGate,
  liveTalkGate,
  liveTalkIsEmptyTranscriptError,
  liveTalkOrbAction,
  liveTalkShouldSendRecording,
  liveTalkDiscardListenOnMute,
  liveTalkMuteA11yKey,
  liveTalkShowsSideChrome,
  liveTalkSilenceDecision,
  type LiveTalkStatus,
} from "@/lib/liveTalkLogic";

const proReady: LiveTalkStatus = {
  enabled: true,
  entitled: true,
  remaining: 12,
  limit: 30,
};

describe("liveTalkAbortRefundNeeded", () => {
  it("refunds only when the client abort beat the first audio clip", () => {
    expect(liveTalkAbortRefundNeeded(false)).toBe(true);
    expect(liveTalkAbortRefundNeeded(true)).toBe(false);
  });
});

describe("liveTalkShouldSendRecording", () => {
  it("does not upload a listen that never crossed speech level", () => {
    expect(liveTalkShouldSendRecording(false)).toBe(false);
    expect(liveTalkShouldSendRecording(true)).toBe(true);
  });
});

describe("liveTalkIsEmptyTranscriptError", () => {
  it("matches the SSE empty-transcript detail", () => {
    expect(liveTalkIsEmptyTranscriptError(new Error("empty_transcript"))).toBe(true);
    expect(liveTalkIsEmptyTranscriptError(new Error("Could not complete live talk"))).toBe(
      false,
    );
  });
});

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
  it("does not mute from the orb; mic control owns mute", () => {
    expect(liveTalkOrbAction("speaking")).toBe("none");
    expect(liveTalkOrbAction("thinking")).toBe("cancelThink");
    expect(liveTalkOrbAction("recording")).toBe("finishListen");
    expect(liveTalkOrbAction("idle")).toBe("begin");
    expect(liveTalkDiscardListenOnMute("recording")).toBe(true);
    expect(liveTalkDiscardListenOnMute("thinking")).toBe(true);
    expect(liveTalkDiscardListenOnMute("speaking")).toBe(false);
    expect(liveTalkMuteA11yKey(false)).toBe("chat.live_talk_mute_a11y");
    expect(liveTalkMuteA11yKey(true)).toBe("chat.live_talk_unmute_a11y");
    expect(liveTalkShowsSideChrome("")).toBe(true);
    expect(liveTalkShowsSideChrome("  ")).toBe(true);
    expect(liveTalkShowsSideChrome("hello")).toBe(false);
  });

  it("offers Speak only while audio is playing", () => {
    expect(liveTalkCanTakeFloor("speaking")).toBe(true);
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
