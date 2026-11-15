import { renderHook } from "@testing-library/react-native";

import {
  playScannerSwitchCue,
  prepareScannerSwitchCue,
  stopScannerSwitchCue,
  useScannerSwitchCue,
} from "@/features/scanner/model/switchCue";
import { loadExpoAudio } from "@/lib/speech/voiceAudio";

jest.mock("expo-file-system/legacy", () => ({
  EncodingType: { Base64: "base64" },
  cacheDirectory: "file:///cache/",
  writeAsStringAsync: jest.fn(async () => undefined),
}));
jest.mock("@/lib/speech/voiceAudio", () => ({ loadExpoAudio: jest.fn() }));

type FakePlayer = {
  uri: string;
  volume: number;
  currentTime: number;
  play: jest.Mock;
  remove: jest.Mock;
  seekTo: jest.Mock;
};

let made: FakePlayer[] = [];

beforeEach(() => {
  stopScannerSwitchCue();
  made = [];
  jest.mocked(loadExpoAudio).mockReturnValue({
    createAudioPlayer: (uri: string) => {
      const player: FakePlayer = {
        uri,
        volume: 1,
        currentTime: 0,
        play: jest.fn(),
        remove: jest.fn(),
        seekTo: jest.fn(async () => {
          player.currentTime = 0;
        }),
      };
      made.push(player);
      return player;
    },
  } as unknown as ReturnType<typeof loadExpoAudio>);
});

it("loads both cues as the scanner opens, so the first switch plays the loaded one", async () => {
  await prepareScannerSwitchCue();
  expect(made.map((player) => player.uri)).toEqual([
    "file:///cache/recall-scanner-switch-forward.wav",
    "file:///cache/recall-scanner-switch-back.wav",
  ]);
  await playScannerSwitchCue(1);
  expect(made).toHaveLength(2);
  expect(made[0].play).toHaveBeenCalledTimes(1);
  expect(made[0].volume).toBe(0.2);
  // Nothing frees the player while it plays: the first cue was released 180 ms in, before a
  // cold player had started, and was never heard.
  expect(made[0].remove).not.toHaveBeenCalled();
});

it("plays a cue again from its start", async () => {
  await playScannerSwitchCue(-1);
  const back = made[1];
  back.currentTime = 0.096;
  await playScannerSwitchCue(-1);
  expect(back.seekTo).toHaveBeenCalledWith(0);
  expect(back.play).toHaveBeenCalledTimes(2);
});

it("frees both cues when the scanner closes, and a cue made as it closes is not kept", async () => {
  await prepareScannerSwitchCue();
  stopScannerSwitchCue();
  expect(made.every((player) => player.remove.mock.calls.length === 1)).toBe(true);
  const preparing = prepareScannerSwitchCue();
  stopScannerSwitchCue();
  await preparing;
  await playScannerSwitchCue(1);
  // The next switch makes its cues again rather than playing a freed one.
  expect(made.at(-2)?.play).toHaveBeenCalledTimes(1);
});

it("stays quiet in a build without audio", async () => {
  jest.mocked(loadExpoAudio).mockReturnValue(null);
  await expect(playScannerSwitchCue(1)).resolves.toBeUndefined();
  expect(made).toHaveLength(0);
});

it("makes the cues while the scanner is open and frees them as it closes", async () => {
  const view = await renderHook(({ visible }: { visible: boolean }) => useScannerSwitchCue(visible), {
    initialProps: { visible: true },
  });
  await Promise.resolve();
  await Promise.resolve();
  await prepareScannerSwitchCue();
  expect(made).toHaveLength(2);
  await view.rerender({ visible: false });
  expect(made.every((player) => player.remove.mock.calls.length === 1)).toBe(true);
});
