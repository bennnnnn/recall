const mockSetAudioModeAsync = jest.fn(async (_mode: unknown) => undefined);
const mockRelease = jest.fn();
const mockPrepare = jest.fn(async (_preset: unknown) => undefined);
const mockRecord = jest.fn();
const mockConstructed = jest.fn((_options: unknown) => undefined);
const mockMetering: { value: number | undefined } = { value: undefined };

jest.mock("expo-file-system/legacy", () => ({
  deleteAsync: jest.fn(async () => undefined),
  getInfoAsync: jest.fn(async () => ({ exists: true, size: 1200 })),
  readAsStringAsync: jest.fn(async () => "ZmFrZQ=="),
}));

jest.mock("expo-modules-core", () => ({
  Platform: { OS: "android" },
  requireOptionalNativeModule: jest.fn(() => ({})),
}));

jest.mock("expo-audio", () => ({
  setAudioModeAsync: (mode: unknown) => mockSetAudioModeAsync(mode),
  RecordingPresets: {
    HIGH_QUALITY: { extension: ".m4a", ios: { audioQuality: 127 }, android: { audioEncoder: "aac" } },
  },
  AudioModule: {
    AudioRecorder: class {
      isRecording = false;
      constructor(options: unknown) {
        mockConstructed(options);
      }
      prepareToRecordAsync = (preset: unknown) => mockPrepare(preset);
      record = () => {
        mockRecord();
        this.isRecording = true;
      };
      getStatus = () => ({ metering: mockMetering.value });
      stop = async () => {
        this.isRecording = false;
      };
      uri = "";
      release = () => mockRelease();
    },
  },
}));

import { startVoiceRecording } from "@/lib/speech/voiceAudio";

describe("startVoiceRecording when the mic cannot start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it.each([
    ["prepare throws", () => mockPrepare.mockRejectedValueOnce(new Error("mic busy"))],
    [
      "record throws",
      () =>
        mockRecord.mockImplementationOnce(() => {
          throw new Error("mic busy");
        }),
    ],
  ])("releases the recorder and restores playback mode when %s", async (_name, arrange) => {
    arrange();

    await expect(startVoiceRecording()).rejects.toThrow("mic busy");

    expect(mockRelease).toHaveBeenCalledTimes(1);
    expect(mockSetAudioModeAsync).toHaveBeenLastCalledWith({
      allowsRecording: false,
      playsInSilentMode: true,
    });
  });

  it("keeps the recorder when recording starts", async () => {
    const recorder = await startVoiceRecording();

    expect(recorder).not.toBeNull();
    expect(mockRelease).not.toHaveBeenCalled();
    expect(mockSetAudioModeAsync).toHaveBeenLastCalledWith({
      allowsRecording: true,
      playsInSilentMode: true,
    });
    // Its level poll runs until the recorder stops.
    await recorder?.stop();
  });
});

describe("startVoiceRecording's level", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });
  afterEach(() => jest.useRealTimers());

  it("builds the recorder with metering on, as Android reads it from the recorder alone", async () => {
    await startVoiceRecording();
    expect(mockConstructed).toHaveBeenCalledWith({
      extension: ".m4a",
      isMeteringEnabled: true,
      audioEncoder: "aac",
    });
  });

  it("hands each reading to the waveform as it changes", async () => {
    const recorder = await startVoiceRecording();
    const levels: number[] = [];
    recorder?.subscribeMetering((level) => levels.push(level));
    for (const db of [-55, -30, -10]) {
      mockMetering.value = db;
      jest.advanceTimersByTime(60);
    }
    expect(levels).toHaveLength(3);
    expect(levels[2]).toBeGreaterThan(levels[1]);
    expect(levels[1]).toBeGreaterThan(levels[0]);
  });
});
