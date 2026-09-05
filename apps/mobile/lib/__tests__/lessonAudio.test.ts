import { createLessonAudio } from "@/lib/lessonAudio";
import { stopSpeaking } from "@/lib/pronunciation";
import { loadExpoAudio } from "@/lib/voiceAudio";
import * as Speech from "expo-speech";
jest.mock("@/lib/pronunciation", () => ({ stopSpeaking: jest.fn() }));
jest.mock("@/lib/voiceAudio", () => ({ loadExpoAudio: jest.fn() }));
jest.mock("expo-speech", () => ({ speak: jest.fn() }));
jest.mock("@/assets/audio/lesson-correct.wav", () => 1);
jest.mock("@/assets/audio/lesson-incorrect.wav", () => 2);
const player = { pause: jest.fn(), remove: jest.fn(), play: jest.fn(), volume: 1 };
const audio = {
  createAudioPlayer: jest.fn(() => player),
  setAudioModeAsync: jest.fn(async () => {}),
};
beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
  jest
    .mocked(loadExpoAudio)
    .mockReturnValue(audio as unknown as NonNullable<ReturnType<typeof loadExpoAudio>>);
});
afterEach(() => {
  jest.useRealTimers();
});
it("plays a gentle effect before localized speech without changing global audio mode", async () => {
  const owner = createLessonAudio(() => true);
  await owner.start("Correcto", "es", true);
  expect(audio.setAudioModeAsync).not.toHaveBeenCalled();
  expect(player.volume).toBe(0.3);
  expect(player.play).toHaveBeenCalledTimes(1);
  expect(Speech.speak).not.toHaveBeenCalled();
  jest.advanceTimersByTime(380);
  expect(Speech.speak).toHaveBeenCalledWith("Correcto", { language: "es", rate: 0.92 });
  owner.stop();
});
it("cancels feedback speech when pronunciation takes over", async () => {
  const owner = createLessonAudio(() => true);
  await owner.start("Correct", "en", true);
  await owner.start("hola", "es");
  jest.advanceTimersByTime(1000);
  expect(Speech.speak).toHaveBeenCalledTimes(1);
  expect(Speech.speak).toHaveBeenCalledWith("hola", expect.anything());
  owner.stop();
});
it("cannot reset recording mode after leaving the lesson", async () => {
  let active = true;
  const owner = createLessonAudio(() => active);
  await owner.start("Correct", "en", true);
  active = false;
  owner.stop();
  audio.setAudioModeAsync.mockClear();
  await audio.setAudioModeAsync();
  jest.advanceTimersByTime(1000);
  await owner.start("Late", "en", true);
  expect(audio.setAudioModeAsync).toHaveBeenCalledTimes(1);
  expect(Speech.speak).not.toHaveBeenCalled();
});
it("does not touch native audio or speech when both outputs are disabled", async () => {
  const owner = createLessonAudio(() => true);
  await owner.start("", "en");
  expect(loadExpoAudio).not.toHaveBeenCalled();
  expect(stopSpeaking).not.toHaveBeenCalled();
  expect(audio.setAudioModeAsync).not.toHaveBeenCalled();
});

it("does not let an old owner cleanup stop the new owner's pronunciation", async () => {
  const old = createLessonAudio(() => true);
  const current = createLessonAudio(() => true);
  await old.start("Correct", "en", true);
  await current.start("hola", "es");
  jest.mocked(stopSpeaking).mockClear();
  old.stop();
  expect(stopSpeaking).not.toHaveBeenCalled();
  current.stop();
});
it("works with visual-only feedback when audio is unavailable", async () => {
  jest.mocked(loadExpoAudio).mockReturnValue(null);
  const owner = createLessonAudio(() => true);
  await expect(owner.start("", "en")).resolves.toBeUndefined();
  expect(Speech.speak).not.toHaveBeenCalled();
  owner.stop();
});
