import { stopSpeaking } from "@/lib/pronunciation";
import { loadExpoAudio } from "@/lib/voiceAudio";

type Player = ReturnType<NonNullable<ReturnType<typeof loadExpoAudio>>["createAudioPlayer"]>;
let active: object | null = null;

/** One lesson owns effects and pronunciation together. No queued speech survives a visit.
 * Effects inherit the active device audio mode; never reconfigure a recording/WebRTC session. */
export function createLessonAudio(isCurrent: () => boolean) {
  const owner = {};
  let generation = 0;
  let player: Player | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  const stop = () => {
    generation += 1;
    if (timer) clearTimeout(timer);
    timer = null;
    try {
      player?.pause();
      player?.remove();
    } catch {
      /* Native teardown is best effort. */
    }
    player = null;
    if (active === owner) {
      active = null;
      stopSpeaking();
    }
  };
  const start = async (text: string, language: string, sound?: boolean) => {
    if (!isCurrent() || (sound === undefined && !text.trim())) return;
    stop();
    stopSpeaking();
    active = owner;
    const run = generation;
    const current = () => active === owner && run === generation && isCurrent();
    try {
      const audio = loadExpoAudio();
      if (!current()) return;
      const speak = () => {
        if (!current() || !text) return;
        try {
          // A synchronous guarded require works in Expo Go and native builds.
          // eslint-disable-next-line @typescript-eslint/no-require-imports
          const speech = require("expo-speech") as typeof import("expo-speech");
          speech.speak(text, { language, rate: 0.92 });
        } catch {
          /* Visual feedback remains available without native speech. */
        }
      };
      if (sound !== undefined && audio) {
        player = audio.createAudioPlayer(
          sound
            ? require("@/assets/audio/lesson-correct.wav")
            : require("@/assets/audio/lesson-incorrect.wav"),
        );
        player.volume = 0.3;
        player.play();
        timer = setTimeout(() => {
          timer = null;
          if (!current()) return;
          try {
            player?.remove();
          } catch {
            /* Already released. */
          }
          player = null;
          speak();
        }, 380);
      } else speak();
    } catch {
      /* Optional audio never blocks practice. */
    }
  };
  return { stop, start };
}
