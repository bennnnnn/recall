jest.mock("expo-file-system/legacy", () => ({
  getInfoAsync: jest.fn(async () => ({ exists: true, size: 1200 })),
  readAsStringAsync: jest.fn(async () => "ZmFrZQ=="),
}));

jest.mock("@/lib/expoRuntime", () => ({
  canUseVoiceInput: jest.fn(() => true),
}));

jest.mock("expo-modules-core", () => ({
  requireOptionalNativeModule: jest.fn(() => null),
}));

jest.mock("expo-audio", () => {
  throw new Error("Cannot find native module 'ExpoAudio'");
});

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

import { canUseVoiceInput } from "@/lib/expoRuntime";
import {
  isVoiceInputAvailable,
  loadExpoAudio,
  normalizeRecordingUri,
  recordingOptionsForFormat,
  speechUploadFromUri,
} from "@/lib/voiceAudio";

const mockCanUseVoiceInput = canUseVoiceInput as jest.MockedFunction<
  typeof canUseVoiceInput
>;

describe("voiceAudio", () => {
  beforeEach(() => {
    mockCanUseVoiceInput.mockReturnValue(true);
  });

  it("skips expo-audio import when voice input is disabled", () => {
    mockCanUseVoiceInput.mockReturnValue(false);
    expect(loadExpoAudio()).toBeNull();
    expect(isVoiceInputAvailable()).toBe(false);
  });

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

  it("uses linear PCM wav options for live talk", () => {
    const options = recordingOptionsForFormat(
      {
        extension: ".m4a",
        ios: { outputFormat: "aac " },
        android: { outputFormat: "mpeg4", audioEncoder: "aac" },
      },
      "wav",
    );
    expect(options.extension).toBe(".wav");
    expect(options.ios?.outputFormat).toBe("lpcm");
    expect(options.android?.extension).toBe(".m4a");
    expect(recordingOptionsForFormat({ extension: ".m4a" }, "aac").extension).toBe(".m4a");
  });

  it("records m4a on Android when wav is requested", () => {
    const { Platform } = jest.requireMock("react-native") as { Platform: { OS: string } };
    Platform.OS = "android";
    try {
      const options = recordingOptionsForFormat({ extension: ".m4a" }, "wav");
      expect(options.extension).toBe(".m4a");
      expect(options.android?.outputFormat).toBe("mpeg4");
      expect(options.android?.audioEncoder).toBe("aac");
    } finally {
      Platform.OS = "ios";
    }
  });
});
