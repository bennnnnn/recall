jest.mock("@/lib/expoRuntime", () => ({
  canUseVoiceInput: jest.fn(() => true),
}));

jest.mock("expo-audio", () => {
  throw new Error("Cannot find native module 'ExpoAudio'");
});

import { canUseVoiceInput } from "@/lib/expoRuntime";
import { isVoiceInputAvailable, loadExpoAudio } from "@/lib/voiceAudio";

const mockCanUseVoiceInput = canUseVoiceInput as jest.MockedFunction<
  typeof canUseVoiceInput
>;

describe("voiceAudio", () => {
  beforeEach(() => {
    mockCanUseVoiceInput.mockReturnValue(true);
  });

  it("skips expo-audio import in Expo Go", async () => {
    mockCanUseVoiceInput.mockReturnValue(false);
    await expect(loadExpoAudio()).resolves.toBeNull();
    await expect(isVoiceInputAvailable()).resolves.toBe(false);
  });

  it("loadExpoAudio returns null when native module is missing", async () => {
    await expect(loadExpoAudio()).resolves.toBeNull();
  });

  it("isVoiceInputAvailable is false when expo-audio fails to load", async () => {
    await expect(isVoiceInputAvailable()).resolves.toBe(false);
  });
});
