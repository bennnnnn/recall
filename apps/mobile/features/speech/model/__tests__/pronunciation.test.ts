import { deleteAsync, writeAsStringAsync } from "expo-file-system/legacy";

import {
  readReplyAloud,
  speakPlainText,
  stopReadingAloud,
  stopSpeaking,
} from "@/features/speech/model/pronunciation";
import {
  pauseReadAloud,
  readAloudSession,
  resumeReadAloud,
} from "@/features/speech/model/readAloudSession";

type StatusListener = (status: {
  didJustFinish?: boolean;
  playing?: boolean;
  currentTime?: number;
  duration?: number;
}) => void;
type FakePlayer = {
  play: jest.Mock;
  pause: jest.Mock;
  remove: jest.Mock;
  addListener: jest.Mock;
  playing: boolean;
  currentTime: number;
  duration: number;
  emit: StatusListener;
};

const mockPlayers: FakePlayer[] = [];
let mockTtsModel = "speech-tts-model";
const mockAppStateHandlers = new Set<(state: string) => void>();

jest.mock("react-native", () => ({
  AppState: {
    addEventListener: (_event: string, handler: (state: string) => void) => {
      mockAppStateHandlers.add(handler);
      return { remove: () => mockAppStateHandlers.delete(handler) };
    },
  },
}));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  EncodingType: { Base64: "base64" },
  writeAsStringAsync: jest.fn(async () => undefined),
  deleteAsync: jest.fn(async () => undefined),
}));
jest.mock("expo-speech", () => ({ speak: jest.fn(), stop: jest.fn() }));
jest.mock("@/lib/api/client", () => ({
  requestRaw: jest.fn(async () => ({
    ok: true,
    json: async () => ({ audio_base64: "QUJD", content_type: "audio/mpeg" }),
  })),
}));
jest.mock("@/lib/speech/voiceAudio", () => ({
  preparePlaybackAudioMode: jest.fn(async () => undefined),
  loadExpoAudio: () => ({
    createAudioPlayer: () => {
      let listener: StatusListener = () => {};
      const player: FakePlayer = {
        play: jest.fn(),
        pause: jest.fn(),
        remove: jest.fn(),
        addListener: jest.fn((_event: string, next: StatusListener) => {
          listener = next;
          return { remove: jest.fn() };
        }),
        playing: false,
        currentTime: 0,
        duration: 0,
        emit: (status) => listener(status),
      };
      mockPlayers.push(player);
      return player;
    },
  }),
}));
jest.mock("@/lib/markdown/plain", () => ({ markdownToSpeechText: (text: string) => text }));
jest.mock("@/features/speech/model/ttsLead", () => ({
  splitTtsChunks: (text: string) => text.split("|"),
}));
jest.mock("@/features/speech/model/ttsPreference", () => ({
  TTS_DEVICE_MODEL: "device",
  TTS_QUALITY_MODEL: "speech-tts-model",
  TTS_FAST_MODEL: "speech-tts-fast-model",
  getTtsModel: async () => mockTtsModel,
}));
jest.mock("@/features/speech/model/speechRate", () => ({
  getSpeechRate: async () => 1,
  currentSpeechRate: () => 1,
}));

async function flush(): Promise<void> {
  for (let i = 0; i < 30; i += 1) await Promise.resolve();
}

describe("cloud read-aloud lifetime", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    mockPlayers.length = 0;
    mockTtsModel = "speech-tts-model";
  });
  afterEach(() => {
    stopSpeaking();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it("releases each clip's player and cache file when the clip ends", async () => {
    const speaking = speakPlainText("hello", "en-US", { token: "tok", preferCloud: true });
    await flush();
    expect(mockPlayers).toHaveLength(1);
    const [player] = mockPlayers;
    player.emit({ playing: true });
    player.emit({ didJustFinish: true });
    await expect(speaking).resolves.toEqual({ ok: true });
    // A finished player kept the audio session in playback until the next
    // tap, and every clip left a recall-tts-*.mp3 behind in the cache.
    expect(player.remove).toHaveBeenCalledTimes(1);
    const path = jest.mocked(writeAsStringAsync).mock.calls[0]?.[0];
    expect(path).toMatch(/^file:\/\/\/cache\/recall-tts-\d+\.mp3$/);
    expect(deleteAsync).toHaveBeenCalledWith(path, { idempotent: true });
  });

  it("stops reading, instead of starting the next clip, when the app goes to the background", async () => {
    const speaking = speakPlainText("first|second", "en-US", { token: "tok", preferCloud: true });
    await flush();
    expect(mockPlayers).toHaveLength(1);
    const [first] = mockPlayers;
    first.emit({ playing: true });

    for (const handler of [...mockAppStateHandlers]) handler("background");
    // expo-audio pauses players natively in the background. The queue read
    // that pause as the end of the clip and played the next one.
    first.playing = false;
    first.emit({ playing: false });
    await flush();
    jest.advanceTimersByTime(1_000);
    await flush();

    expect(mockPlayers).toHaveLength(1);
    expect(first.remove).toHaveBeenCalled();
    await expect(speaking).resolves.toEqual({ ok: true });
  });

  it("keeps reading across an inactive blip", async () => {
    const speaking = speakPlainText("first|second", "en-US", { token: "tok", preferCloud: true });
    await flush();
    const [first] = mockPlayers;
    first.emit({ playing: true });
    for (const handler of [...mockAppStateHandlers]) handler("inactive");
    expect(first.remove).not.toHaveBeenCalled();
    first.emit({ didJustFinish: true });
    await flush();
    expect(mockPlayers).toHaveLength(2);
    mockPlayers[1].emit({ didJustFinish: true });
    await expect(speaking).resolves.toEqual({ ok: true });
  });
});

describe("the on-device voice switch", () => {
  const { requestRaw } = jest.requireMock<{ requestRaw: jest.Mock }>("@/lib/api/client");
  const { speak } = jest.requireMock<{ speak: jest.Mock }>("expo-speech");

  beforeEach(() => {
    jest.clearAllMocks();
    mockPlayers.length = 0;
  });
  afterEach(() => {
    stopSpeaking();
    mockTtsModel = "speech-tts-model";
  });

  it("reads with the phone's voice for a paid user who switched it on", async () => {
    mockTtsModel = "device";
    void speakPlainText("hello", "en-US", { token: "tok", preferCloud: true });
    await flush();
    expect(requestRaw).not.toHaveBeenCalled();
    expect(speak).toHaveBeenCalledWith("hello", expect.anything());
  });

  it("uses the cloud voice for a paid user who left it off", async () => {
    void speakPlainText("hello", "en-US", { token: "tok", preferCloud: true });
    await flush();
    expect(requestRaw).toHaveBeenCalled();
    expect(speak).not.toHaveBeenCalled();
  });
});

describe("the read-aloud player", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    mockPlayers.length = 0;
    mockTtsModel = "speech-tts-model";
  });
  afterEach(() => {
    stopReadingAloud();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it("holds a paused clip, rather than taking it for finished, and plays on after resume", async () => {
    const reading = readReplyAloud("m1", "first|second", "en-US", { token: "tok", preferCloud: true });
    expect(readAloudSession.get()).toMatchObject({ messageId: "m1", phase: "preparing" });
    await flush();
    expect(readAloudSession.get()).toMatchObject({ phase: "playing", canPause: true, progress: 0 });
    const [first] = mockPlayers;
    first.emit({ playing: true, currentTime: 1, duration: 2 });
    // Two clips: halfway through the first is a quarter of the reply.
    expect(readAloudSession.get()?.progress).toBe(0.25);

    pauseReadAloud();
    expect(first.pause).toHaveBeenCalled();
    first.playing = false;
    first.emit({ playing: false });
    await flush();
    jest.advanceTimersByTime(1_000);
    await flush();
    // The pause stopped the clip; the queue did not read that as its end.
    expect(mockPlayers).toHaveLength(1);
    expect(readAloudSession.get()?.phase).toBe("paused");

    resumeReadAloud();
    expect(first.play).toHaveBeenCalledTimes(2);
    expect(readAloudSession.get()?.phase).toBe("playing");
    first.emit({ didJustFinish: true });
    await flush();
    expect(mockPlayers).toHaveLength(2);
    mockPlayers[1].emit({ didJustFinish: true });
    await expect(reading).resolves.toEqual({ ok: true });
    expect(readAloudSession.get()).toBeNull();
  });

  it("cancels the next clip's download on Stop, and the cancel is no failure", async () => {
    const { requestRaw } = jest.requireMock<{ requestRaw: jest.Mock }>("@/lib/api/client");
    const signals: AbortSignal[] = [];
    // The lead downloads; the clip after it waits until Stop cancels it, then rejects as the
    // API client rejects a cancel. Nothing awaited that download: its rejection went unhandled.
    requestRaw
      .mockImplementationOnce(async () => ({
        ok: true,
        json: async () => ({ audio_base64: "QUJD", content_type: "audio/mpeg" }),
      }))
      .mockImplementationOnce(
        (_path: string, _token: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            if (init.signal) signals.push(init.signal);
            init.signal?.addEventListener("abort", () =>
              reject(Object.assign(new Error("Request canceled"), { name: "AbortError" })),
            );
          }),
      );
    const reading = readReplyAloud("m1", "lead|rest", "en-US", { token: "tok", preferCloud: true });
    await flush();
    mockPlayers[0].emit({ playing: true });
    expect(signals).toHaveLength(1);

    stopReadingAloud();
    await flush();

    expect(signals[0]?.aborted).toBe(true);
    await expect(reading).resolves.toEqual({ ok: true });
  });

  it("reads on with the phone's voice when a later clip's download runs out of time", async () => {
    const { requestRaw } = jest.requireMock<{ requestRaw: jest.Mock }>("@/lib/api/client");
    const { speak } = jest.requireMock<{ speak: jest.Mock }>("expo-speech");
    const info = jest.spyOn(console, "info").mockImplementation(() => {});
    // The lead downloads; every later request reaches its own deadline (an AbortError, the
    // reading's signal untouched). Taken for a Stop, the reading ended silently mid-reply.
    requestRaw
      .mockImplementationOnce(async () => ({
        ok: true,
        json: async () => ({ audio_base64: "QUJD", content_type: "audio/mpeg" }),
      }))
      .mockImplementation(async () => {
        throw Object.assign(new Error("Request canceled"), { name: "AbortError" });
      });
    void readReplyAloud("m1", "lead|timed out", "en-US", { token: "tok", preferCloud: true });
    await flush();
    mockPlayers[0].emit({ didJustFinish: true });
    await flush();

    expect(speak).toHaveBeenCalledWith("lead|timed out", expect.anything());
    requestRaw.mockReset();
    requestRaw.mockImplementation(async () => ({
      ok: true,
      json: async () => ({ audio_base64: "QUJD", content_type: "audio/mpeg" }),
    }));
    info.mockRestore();
  });

  it("closes the player and ends the reading on Stop", async () => {
    const reading = readReplyAloud("m1", "first|second", "en-US", { token: "tok", preferCloud: true });
    await flush();
    mockPlayers[0].emit({ playing: true });
    stopReadingAloud();
    expect(readAloudSession.get()).toBeNull();
    await expect(reading).resolves.toEqual({ ok: true });
    expect(mockPlayers[0].remove).toHaveBeenCalled();
  });

  it("keeps the player of the reply read next when the one before ends", async () => {
    const firstReading = readReplyAloud("m1", "one", "en-US", { token: "tok", preferCloud: true });
    await flush();
    const secondReading = readReplyAloud("m2", "two", "en-US", { token: "tok", preferCloud: true });
    await expect(firstReading).resolves.toEqual({ ok: true });
    expect(readAloudSession.get()?.messageId).toBe("m2");
    await flush();
    mockPlayers[mockPlayers.length - 1].emit({ didJustFinish: true });
    await expect(secondReading).resolves.toEqual({ ok: true });
  });
});
