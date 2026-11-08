import { speechApi } from "@/features/speech/api";
import { liveTalkErrorGate } from "@/features/speech/model/liveTalkLogic";
import { createRealtimeVoiceSession } from "@/features/speech/model/realtimeVoice";
import * as webrtc from "react-native-webrtc";

const mockSteps: string[] = [];
const mockInterruptListeners = new Set<() => void>();
const mockCallAudio = {
  startAsync: jest.fn(async (): Promise<void> => {
    mockSteps.push("route");
  }),
  stopAsync: jest.fn(async () => {
    mockSteps.push("unroute");
  }),
  addListener: jest.fn((event: string, listener: () => void) => {
    if (event === "onInterrupted") mockInterruptListeners.add(listener);
    return { remove: () => mockInterruptListeners.delete(listener) };
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

type Deferred<T> = { promise: Promise<T>; resolve: (value: T) => void };
function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

describe("a live talk call plays on the call's route (loudspeaker or headset), not the earpiece", () => {
  const track = { kind: "audio", enabled: true, stop: jest.fn() };

  const releases: jest.Mock[] = [];
  /** The offer each peer makes: the default answers at once; a test may hold it. */
  let createOffer: jest.Mock;
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
    mockInterruptListeners.clear();
    releases.length = 0;
    (globalThis as unknown as { __DEV__: boolean }).__DEV__ = false;
    microphone([track]);
    createOffer = jest.fn(async () => ({ sdp: "v=0\nm=audio" }));
    // Each call its own data channel, which opens once the answer is applied.
    (webrtc.RTCPeerConnection as unknown as jest.Mock).mockImplementation(() => {
      const channel: { readyState: string; send: jest.Mock; close: jest.Mock; onopen?: () => void } = {
        readyState: "open", send: jest.fn(), close: jest.fn(),
      };
      return {
        iceGatheringState: "complete",
        addTrack: jest.fn(),
        createDataChannel: () => channel,
        createOffer,
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
    expect(jest.mocked(speechApi.endRealtimeSession).mock.calls).toEqual([["tok", "call-1"]]);
    // The exchange's request was cancelled with the call, not left to open one on the server.
    const signal = jest.mocked(speechApi.connectRealtimeSession).mock.calls[0]?.[3];
    expect(signal?.aborted).toBe(true);
  });

  // Each stage the call waits on before the offer goes out: a hang-up there sent the offer
  // anyway, and the server opened an OpenAI call for a phone that had left.
  it.each([
    ["the offer is made", "offer"],
    ["the session is minted", "mint"],
  ] as const)("sends no offer when the call hangs up while %s", async (_stage, held) => {
    const offer = deferred<{ sdp: string }>();
    const mint = deferred<{ call_id: string; model: string; expires_at: number }>();
    if (held === "offer") createOffer.mockReturnValueOnce(offer.promise);
    else jest.mocked(speechApi.createRealtimeSession).mockReturnValueOnce(mint.promise);
    const hangUp = new AbortController();
    const connecting = createRealtimeVoiceSession({
      token: "tok", chatId: "chat-1", onEvent: () => {}, signal: hangUp.signal,
    });
    await flush();

    hangUp.abort();
    await expect(connecting).rejects.toMatchObject({ name: "AbortError" });
    offer.resolve({ sdp: "v=0\nm=audio" });
    mint.resolve({ call_id: "call-1", model: "m", expires_at: 1 });
    await flush();
    await flush();

    expect(speechApi.connectRealtimeSession).not.toHaveBeenCalled();
    // The minted minutes go back once.
    expect(jest.mocked(speechApi.endRealtimeSession).mock.calls).toEqual([["tok", "call-1"]]);
    expect(mockCallAudio.stopAsync).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["the route is taken", "route"],
    ["the microphone opens", "microphone"],
  ] as const)("mints nothing and gives everything back when the call hangs up while %s", async (_stage, held) => {
    const routed = deferred<void>();
    const opened = deferred<void>();
    if (held === "route") mockCallAudio.startAsync.mockReturnValueOnce(routed.promise);
    else {
      (webrtc.mediaDevices.getUserMedia as jest.Mock).mockImplementationOnce(async () => {
        await opened.promise;
        const release = jest.fn();
        releases.push(release);
        return { getAudioTracks: () => [track], getTracks: () => [track], release };
      });
    }
    const hangUp = new AbortController();
    const connecting = createRealtimeVoiceSession({
      token: "tok", chatId: "chat-1", onEvent: () => {}, signal: hangUp.signal,
    }).catch((error: unknown) => error);
    await flush();

    hangUp.abort();
    routed.resolve();
    opened.resolve();
    expect(await connecting).toMatchObject({ name: "AbortError" });
    await flush();

    expect(webrtc.mediaDevices.getUserMedia).toHaveBeenCalledTimes(held === "route" ? 0 : 1);
    expect(releases.every((release) => release.mock.calls.length === 1)).toBe(true);
    expect(speechApi.createRealtimeSession).not.toHaveBeenCalled();
    expect(mockCallAudio.stopAsync).toHaveBeenCalledTimes(1);
    expect(mockInterruptListeners.size).toBe(0);
  });

  it("says when a phone call or another app takes the audio, until the call hangs up", async () => {
    const onEvent = jest.fn();
    const session = await createRealtimeVoiceSession({ token: "tok", chatId: "chat-1", onEvent });
    mockInterruptListeners.forEach((listener) => listener());
    expect(onEvent).toHaveBeenCalledWith({ type: "interrupted" });

    session.close();
    expect(mockInterruptListeners.size).toBe(0);
  });

  it("does not start while the phone is on a call, and takes neither the mic nor minutes", async () => {
    mockCallAudio.startAsync.mockRejectedValueOnce(
      Object.assign(new Error("The phone is on a call"), { code: "ERR_AUDIO_FOCUS_REFUSED" }),
    );
    const error = await createRealtimeVoiceSession({ token: "tok", chatId: "chat-1", onEvent: () => {} })
      .catch((caught: unknown) => caught);

    expect(liveTalkErrorGate(error)).toBe("phone_busy");
    expect(webrtc.mediaDevices.getUserMedia).not.toHaveBeenCalled();
    expect(speechApi.createRealtimeSession).not.toHaveBeenCalled();
    expect(mockInterruptListeners.size).toBe(0);
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
});
