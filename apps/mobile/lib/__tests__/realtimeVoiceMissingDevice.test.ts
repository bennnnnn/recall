jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));
jest.mock("expo-device", () => {
  throw new Error("Cannot find native module 'ExpoDevice'");
});
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

  it("keeps AEC when this binary was built before expo-device", () => {
    expect(webRtcMicConstraints()).toEqual({
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    });
  });
});
