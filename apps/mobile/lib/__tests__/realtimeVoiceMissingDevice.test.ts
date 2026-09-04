jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));
jest.mock("expo-modules-core", () => ({
  requireOptionalNativeModule: () => null,
}));
jest.mock("@/lib/voiceAudio", () => ({
  yieldMicToWebRtc: jest.fn(async () => undefined),
}));
jest.mock("react-native-webrtc", () => ({
  __WEBRTC_STUB__: true,
}));
jest.mock("@/lib/api/speech", () => ({
  speechApi: { createRealtimeSession: jest.fn() },
}));

import { isRealtimeVoiceAvailable, webRtcMicConstraints } from "@/lib/realtimeVoice";

describe("realtimeVoice without ExpoDevice", () => {
  it("imports without crashing when the native module is missing", () => {
    expect(isRealtimeVoiceAvailable()).toBe(false);
  });

  it("uses the Simulator mic path when this binary was built before expo-device", () => {
    expect(webRtcMicConstraints()).toEqual({
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    });
  });
});
