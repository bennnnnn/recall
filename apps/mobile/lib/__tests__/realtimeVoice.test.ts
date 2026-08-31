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
  speechApi: { exchangeRealtimeSdp: jest.fn() },
}));

import { createRealtimeVoiceSession, isRealtimeVoiceAvailable, webRtcMicConstraints } from "@/lib/realtimeVoice";

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

  it("disables iOS VoiceProcessing so Simulator CoreAudio does not deadlock", () => {
    expect(webRtcMicConstraints()).toEqual({
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    });
  });
});
