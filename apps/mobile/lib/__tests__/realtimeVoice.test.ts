jest.mock("react-native", () => ({
  NativeModules: {},
  TurboModuleRegistry: { get: () => null },
}));

jest.mock("@/lib/api/speech", () => ({
  speechApi: { exchangeRealtimeSdp: jest.fn() },
}));

import { createRealtimeVoiceSession, isRealtimeVoiceAvailable } from "@/lib/realtimeVoice";

describe("realtimeVoice", () => {
  it("is unavailable when the native WebRTC module is not linked", () => {
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
});
