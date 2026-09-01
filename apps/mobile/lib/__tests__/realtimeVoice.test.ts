jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

jest.mock("@/lib/voiceAudio", () => ({
  yieldMicToWebRtc: jest.fn(async () => undefined),
}));

jest.mock("react-native-webrtc", () => ({
  __WEBRTC_STUB__: true,
}));

jest.mock("@/lib/api/speech", () => ({
  speechApi: { exchangeRealtimeSdp: jest.fn(), createRealtimeSession: jest.fn() },
}));

import {
  createRealtimeVoiceSession,
  isRealtimeVoiceAvailable,
  realtimeTranscriptRejectionReason,
  webRtcMicConstraints,
} from "@/lib/realtimeVoice";

describe("realtimeVoice", () => {
  it("is unavailable when Metro resolved the WebRTC stub", () => {
    expect(isRealtimeVoiceAvailable()).toBe(false);
  });

  it("does not crash chat when opening Live Talk without WebRTC", async () => {
    await expect(
      createRealtimeVoiceSession({
        token: "tok",
        onEvent: () => undefined,
      }),
    ).rejects.toThrow("webrtc_unavailable");
  });

  it("keeps the simulator-safe iOS capture constraints", () => {
    expect(webRtcMicConstraints()).toEqual({
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    });
  });

  it("accepts an ordinary completed user transcript", () => {
    expect(
      realtimeTranscriptRejectionReason({
        text: "Can you explain this to me?",
        suppressed: false,
        vadDurationMs: 1600,
        averageLogprob: -0.3,
      }),
    ).toBeNull();
  });

  it("rejects a turn captured during assistant playback", () => {
    expect(
      realtimeTranscriptRejectionReason({
        text: "Hi there",
        suppressed: true,
        vadDurationMs: 1400,
      }),
    ).toBe("assistant_playback");
  });

  it("rejects known silence hallucinations", () => {
    expect(
      realtimeTranscriptRejectionReason({
        text: "Thank you for watching.",
        suppressed: false,
        vadDurationMs: 1600,
      }),
    ).toBe("known_silence_hallucination");
  });

  it("rejects assistant echo near playback", () => {
    expect(
      realtimeTranscriptRejectionReason({
        text: "How can I help you",
        suppressed: false,
        vadDurationMs: 1800,
        recentAssistantText: "Hi there. How can I help you today?",
        nearAssistantPlayback: true,
      }),
    ).toBe("assistant_echo");
  });

  it("rejects very short VAD impulses and very-low-confidence transcripts", () => {
    expect(
      realtimeTranscriptRejectionReason({
        text: "There",
        suppressed: false,
        vadDurationMs: 930,
      }),
    ).toBe("vad_impulse");
    expect(
      realtimeTranscriptRejectionReason({
        text: "unreliable phrase",
        suppressed: false,
        vadDurationMs: 1800,
        averageLogprob: -4,
      }),
    ).toBe("very_low_confidence");
  });
});
