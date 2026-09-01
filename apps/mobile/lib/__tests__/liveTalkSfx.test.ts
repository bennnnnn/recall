const mockPlay = jest.fn();
const mockCreateAudioPlayer = jest.fn(() => ({
  play: mockPlay,
  remove: jest.fn(),
}));
const mockNotifySuccess = jest.fn();
const mockTap = jest.fn();

jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "/tmp/",
  writeAsStringAsync: jest.fn(async () => undefined),
  EncodingType: { Base64: "base64" },
}));

jest.mock("@/lib/haptics", () => ({
  notifySuccess: () => mockNotifySuccess(),
  tap: () => mockTap(),
}));

jest.mock("@/lib/voiceAudio", () => ({
  loadExpoAudio: () => ({ createAudioPlayer: mockCreateAudioPlayer }),
}));

import {
  LIVE_TALK_CUE_TONES,
  buildLiveTalkCueWavBase64,
  liveTalkCueForVisibility,
  playLiveTalkCue,
} from "@/lib/liveTalkSfx";

describe("liveTalkSfx", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("encodes distinct rising start and falling end chimes as WAV", () => {
    const start = buildLiveTalkCueWavBase64("start");
    const end = buildLiveTalkCueWavBase64("end");
    expect(start.startsWith("UklGR")).toBe(true);
    expect(start).not.toEqual(end);
    expect(LIVE_TALK_CUE_TONES.start[0]?.hz).toBeLessThan(LIVE_TALK_CUE_TONES.start[1]?.hz ?? 0);
    expect(LIVE_TALK_CUE_TONES.end[0]?.hz).toBeGreaterThan(LIVE_TALK_CUE_TONES.end[1]?.hz ?? 0);
  });

  it("maps overlay visibility to open and close cues", () => {
    expect(liveTalkCueForVisibility(false, false)).toBeNull();
    expect(liveTalkCueForVisibility(true, false)).toBe("start");
    expect(liveTalkCueForVisibility(true, true)).toBeNull();
    expect(liveTalkCueForVisibility(false, true)).toBe("end");
  });

  it("plays start with a success haptic and end with a tap, without awaiting connect", async () => {
    playLiveTalkCue("start");
    playLiveTalkCue("end");
    expect(mockNotifySuccess).toHaveBeenCalledTimes(1);
    expect(mockTap).toHaveBeenCalledTimes(1);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(mockCreateAudioPlayer).toHaveBeenCalled();
    expect(mockPlay).toHaveBeenCalled();
  });
});
