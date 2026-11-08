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
// expo-audio's setAudioModeAsync resets Android's mode and speakerphone: a call never asks for it.
jest.mock("@/lib/speech/voiceAudio", () => ({
  yieldMicToWebRtc: jest.fn(async () => undefined),
  preparePlaybackAudioMode: jest.fn(async () => undefined),
}));
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

  const releases: jest.Mock[] = [];
  function microphone(tracks: unknown[]) {
    (webrtc.mediaDevices.getUserMedia as jest.Mock).mockImplementation(async () => {
      mockSteps.push("microphone");
      const release = jest.fn();
      releases.push(release);
      return { getAudioTracks: () => tracks, getTracks: () => tracks, release };
    });
  }

  beforeEach(() => {
    jest.clearAllMocks();
    mockSteps.length = 0;
    releases.length = 0;
    (globalThis as unknown as { __DEV__: boolean }).__DEV__ = false;
    microphone([track]);
    // Each call its own data channel, which opens once the answer is applied.
    (webrtc.RTCPeerConnection as unknown as jest.Mock).mockImplementation(() => {
      const channel: { readyState: string; send: jest.Mock; close: jest.Mock; onopen?: () => void } = {
        readyState: "open", send: jest.fn(), close: jest.fn(),
      };
      return {
        iceGatheringState: "complete",
        addTrack: jest.fn(),
        createDataChannel: () => channel,
        createOffer: async () => ({ sdp: "v=0\nm=audio" }),
        setLocalDescription: async () => undefined,
        setRemoteDescription: async () => {
          channel.onopen?.();
        },
        close: jest.fn(),
        getReceivers: () => [],
      };
    });
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

  it("gives the route, the mic and the minutes back at once on a hang-up while it connects", async () => {
    (speechApi.connectRealtimeSession as jest.Mock).mockReturnValueOnce(new Promise(() => {}));
    const hangUp = new AbortController();
    const connecting = createRealtimeVoiceSession({
      token: "tok", chatId: "chat-1", onEvent: () => {}, signal: hangUp.signal,
    });
    await flush();
    expect(mockCallAudio.stopAsync).not.toHaveBeenCalled();

    hangUp.abort();
    // The connect never answered: the hang-up did not wait for it.
    await expect(connecting).rejects.toMatchObject({ name: "AbortError" });
    await flush();
    expect(mockCallAudio.stopAsync).toHaveBeenCalledTimes(1);
    expect(track.stop).toHaveBeenCalled();
    expect(releases[0]).toHaveBeenCalledTimes(1);
    expect(speechApi.endRealtimeSession).toHaveBeenCalledWith("tok", "call-1");
  });

  it("keeps the live call's route when the call before it hangs up late", async () => {
    let answerStale!: (value: { sdp: string }) => void;
    (speechApi.connectRealtimeSession as jest.Mock).mockReturnValueOnce(
      new Promise((resolve) => {
        answerStale = resolve;
      }),
    );
    const stale = createRealtimeVoiceSession({ token: "tok", chatId: "chat-1", onEvent: () => {} });
    await flush();
    const live = await createRealtimeVoiceSession({ token: "tok", chatId: "chat-1", onEvent: () => {} });

    // The stale call connects after the live one and is hung up then, as useLiveTalk does.
    answerStale({ sdp: "v=0\nm=audio" });
    (await stale).close();
    await flush();
    expect(mockCallAudio.stopAsync).not.toHaveBeenCalled();

    live.close();
    await flush();
    expect(mockCallAudio.stopAsync).toHaveBeenCalledTimes(1);
  });

  it("gives the route and the mic back when the peer cannot be built", async () => {
    (webrtc.RTCPeerConnection as unknown as jest.Mock).mockImplementationOnce(() => {
      throw new Error("no peer");
    });
    await expect(
      createRealtimeVoiceSession({ token: "tok", chatId: "chat-1", onEvent: () => {} }),
    ).rejects.toThrow("no peer");
    expect(mockCallAudio.stopAsync).toHaveBeenCalledTimes(1);
    expect(releases[0]).toHaveBeenCalledTimes(1);
  });

  it("never resets expo-audio's mode during a call", async () => {
    const { preparePlaybackAudioMode } = jest.requireMock<{ preparePlaybackAudioMode: jest.Mock }>(
      "@/lib/speech/voiceAudio",
    );
    const session = await createRealtimeVoiceSession({ token: "tok", chatId: "chat-1", onEvent: () => {} });
    session.close();
    await flush();
    expect(preparePlaybackAudioMode).not.toHaveBeenCalled();
  });
});
