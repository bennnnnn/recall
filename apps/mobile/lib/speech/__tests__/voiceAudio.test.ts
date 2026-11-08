jest.mock("expo-file-system/legacy", () => ({
  getInfoAsync: jest.fn(async () => ({ exists: true, size: 1200 })),
  readAsStringAsync: jest.fn(async () => "ZmFrZQ=="),
}));

jest.mock("expo-modules-core", () => ({
  requireOptionalNativeModule: jest.fn(() => null),
}));

jest.mock("expo-audio", () => {
  throw new Error("Cannot find native module 'ExpoAudio'");
});

import {
  isVoiceInputAvailable,
  loadExpoAudio,
  meteredRecordingOptions,
  meteringLevel,
  nativeRecorderOptions,
  normalizeRecordingUri,
  speechUploadFromUri,
} from "@/lib/speech/voiceAudio";

describe("voiceAudio", () => {
  it("loadExpoAudio returns null when native module is missing", () => {
    expect(loadExpoAudio()).toBeNull();
  });

  it("isVoiceInputAvailable is false when expo-audio fails to load", () => {
    expect(isVoiceInputAvailable()).toBe(false);
  });

  it("normalizes recording uri", () => {
    expect(normalizeRecordingUri("/tmp/speech.m4a")).toBe("file:///tmp/speech.m4a");
    expect(normalizeRecordingUri("file:///tmp/speech.m4a")).toBe("file:///tmp/speech.m4a");
  });

  it("builds upload metadata from uri", () => {
    expect(speechUploadFromUri("file:///cache/recording.m4a")).toEqual({
      uri: "file:///cache/recording.m4a",
      name: "recording.m4a",
      type: "audio/m4a",
    });
    expect(speechUploadFromUri("file:///cache/speech.wav")).toEqual({
      uri: "file:///cache/speech.wav",
      name: "speech.wav",
      type: "audio/wav",
    });
  });

  it("records Expo's high-quality preset with metering on", () => {
    expect(meteredRecordingOptions({ extension: ".m4a", sampleRate: 44100 })).toEqual({
      extension: ".m4a",
      sampleRate: 44100,
      isMeteringEnabled: true,
    });
  });

  it("builds the native recorder with metering on and this platform's own block", () => {
    const preset = meteredRecordingOptions({
      extension: ".m4a",
      sampleRate: 44100,
      android: { outputFormat: "mpeg4", audioEncoder: "aac" },
      ios: { audioQuality: 127 },
      web: { mimeType: "audio/webm" },
    });
    // Android reads metering's switch from the recorder's own options only: built with `{}`,
    // it never reported a level and the waveform barely moved.
    expect(nativeRecorderOptions(preset, "android")).toEqual({
      extension: ".m4a",
      sampleRate: 44100,
      isMeteringEnabled: true,
      outputFormat: "mpeg4",
      audioEncoder: "aac",
    });
    expect(nativeRecorderOptions(preset, "ios")).toEqual({
      extension: ".m4a",
      sampleRate: 44100,
      isMeteringEnabled: true,
      audioQuality: 127,
    });
  });
});

describe("the dictation waveform's level", () => {
  it("rests low with no reading", () => {
    expect(meteringLevel(undefined, "average")).toBe(0.12);
    expect(meteringLevel(-160, "peak")).toBe(0.12);
  });

  it("maps iOS's average power from -60 dB (floor) to 0 dB (full)", () => {
    expect(meteringLevel(-60, "average")).toBeCloseTo(0.1);
    expect(meteringLevel(-30, "average")).toBeCloseTo(0.55);
    expect(meteringLevel(0, "average")).toBeCloseTo(1);
  });

  it("draws Android's peak readings as the average they stand for", () => {
    // The same voice: its peaks read about 12 dB over its average power.
    expect(meteringLevel(-18, "peak")).toBeCloseTo(meteringLevel(-30, "average"));
    // A quiet room's peaks stay near the floor; speech and a loud voice climb the bars.
    expect(meteringLevel(-50, "peak")).toBeLessThan(0.2);
    expect(meteringLevel(-15, "peak")).toBeGreaterThan(0.55);
    expect(meteringLevel(-3, "peak")).toBeGreaterThan(0.75);
    expect(meteringLevel(0, "peak")).toBeLessThanOrEqual(1);
  });

  it("moves with the voice on both platforms", () => {
    for (const kind of ["average", "peak"] as const) {
      const levels = [-55, -40, -25, -10].map((db) => meteringLevel(db, kind));
      expect(levels).toEqual([...levels].sort((a, b) => a - b));
      expect(levels[3] - levels[0]).toBeGreaterThan(0.45);
    }
  });
});
