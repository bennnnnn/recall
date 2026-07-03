jest.mock("expo-file-system/legacy", () => ({
  getInfoAsync: jest.fn(async () => ({ exists: true, size: 1200 })),
  readAsStringAsync: jest.fn(async () => "ZmFrZQ=="),
}));

jest.mock("@/lib/expoRuntime", () => ({
  canUseVoiceInput: jest.fn(() => true),
}));

jest.mock("expo-audio", () => {
  throw new Error("Cannot find native module 'ExpoAudio'");
});

import { canUseVoiceInput } from "@/lib/expoRuntime";
import {
  isVoiceInputAvailable,
  loadExpoAudio,
  normalizeRecordingUri,
  speechUploadFromUri,
} from "@/lib/voiceAudio";

const mockCanUseVoiceInput = canUseVoiceInput as jest.MockedFunction<
  typeof canUseVoiceInput
>;

describe("voiceAudio", () => {
  beforeEach(() => {
    mockCanUseVoiceInput.mockReturnValue(true);
  });

  it("skips expo-audio import in Expo Go", () => {
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
  });
});
