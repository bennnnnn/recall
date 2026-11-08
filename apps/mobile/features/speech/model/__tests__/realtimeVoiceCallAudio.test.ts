import { speechApi } from "@/features/speech/api";
import { createRealtimeVoiceSession } from "@/features/speech/model/realtimeVoice";
import * as webrtc from "react-native-webrtc";

const mockSteps: string[] = [];
const mockCallAudio = {
  startAsync: jest.fn(async () => {
    mockSteps.push("route");
  }),
  stopAsync: jest.fn(async () => {
    mockSteps.push("unroute");
  }),
};

jest.mock("react-native", () => ({
  Platform: { OS: "android" },
  NativeModules: { WebRTCModule: {} },
  TurboModuleRegistry: { get: (name: string) => (name === "WebRTCModule" ? {} : null) },
}));
jest.mock("expo-modules-core", () => ({
  requireOptionalNativeModule: (name: string) =>
    name === "RecallCallAudio" ? mockCallAudio : { isDevice: true },
}));
jest.mock("expo-constants", () => ({}));
jest.mock("@/lib/speech/voiceAudio", () => ({ yieldMicToWebRtc: jest.fn(async () => undefined) }));
jest.mock("@/features/speech/api", () => ({
  speechApi: {
    createRealtimeSession: jest.fn(),
    connectRealtimeSession: jest.fn(),
    endRealtimeSession: jest.fn(async () => ({})),
    realtimeTool: jest.fn(),
  },
}));
jest.mock("react-native-webrtc", () => ({
  mediaDevices: { getUserMedia: jest.fn() },
  RTCPeerConnection: jest.fn(),
  RTCSessionDescription: jest.fn((value) => value),
}));

const flush = () => new Promise<void>((done) => setImmediate(() => done()));

describe("a live talk call plays on the call's route (loudspeaker or headset), not the earpiece", () => {
  const track = { kind: "audio", enabled: true, stop: jest.fn() };
  let channel: { readyState: string; send: jest.Mock; close: jest.Mock; onopen?: () => void };

  function microphone(tracks: unknown[]) {
    (webrtc.mediaDevices.getUserMedia as jest.Mock).mockImplementation(async () => {
      mockSteps.push("microphone");
      return { getAudioTracks: () => tracks, getTracks: () => tracks, release: jest.fn() };
    });
  }

  beforeEach(() => {
    jest.clearAllMocks();
    mockSteps.length = 0;
    (globalThis as unknown as { __DEV__: boolean }).__DEV__ = false;
    channel = { readyState: "open", send: jest.fn(), close: jest.fn() };
    microphone([track]);
    (webrtc.RTCPeerConnection as unknown as jest.Mock).mockImplementation(() => ({
      addTrack: jest.fn(),
      createDataChannel: () => channel,
      createOffer: async () => ({ sdp: "v=0\nm=audio" }),
      setLocalDescription: async () => undefined,
      setRemoteDescription: async () => {
        channel.onopen?.();
      },
      close: jest.fn(),
      getReceivers: () => [],
    }));
    (speechApi.createRealtimeSession as jest.Mock).mockResolvedValue({ call_id: "call-1", model: "m", expires_at: 1 });
    (speechApi.connectRealtimeSession as jest.Mock).mockResolvedValue({ sdp: "v=0\nm=audio" });
  });

  it("routes the call before WebRTC opens the microphone, and gives the route back on hang-up", async () => {
    const session = await createRealtimeVoiceSession({ token: "tok", chatId: "chat-1", onEvent: () => {} });
    expect(mockSteps).toEqual(["route", "microphone"]);

    session.close();
    session.close();
    await flush();
    expect(mockCallAudio.stopAsync).toHaveBeenCalledTimes(1);
    expect(mockSteps).toEqual(["route", "microphone", "unroute"]);
  });

  it("gives the route back when the microphone gives no audio", async () => {
    microphone([]);
    await expect(
      createRealtimeVoiceSession({ token: "tok", chatId: "chat-1", onEvent: () => {} }),
    ).rejects.toThrow("microphone_unavailable");
    expect(mockCallAudio.stopAsync).toHaveBeenCalledTimes(1);
  });

  it("gives the route back when the call cannot connect", async () => {
    (speechApi.connectRealtimeSession as jest.Mock).mockRejectedValueOnce(new Error("network down"));
    await expect(
      createRealtimeVoiceSession({ token: "tok", chatId: "chat-1", onEvent: () => {} }),
    ).rejects.toThrow("network down");
    expect(mockCallAudio.stopAsync).toHaveBeenCalledTimes(1);
  });
});
