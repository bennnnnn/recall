/** Device TTS via expo-speech; Whisper/pronunciation_url later. */

import { markdownToPlainText } from "@/lib/markdownPlain";
import { canUseVoiceInput } from "@/lib/expoRuntime";

type SpeechModule = typeof import("expo-speech");

/** undefined = not loaded yet; null = unavailable or failed to load. */
let speechModule: SpeechModule | null | undefined;

/** Sync require keeps expo-speech in the main bundle (async import() breaks Metro module IDs). */
function loadSpeech(): SpeechModule | null {
  if (!canUseVoiceInput()) {
    speechModule = null;
    return null;
  }
  if (speechModule === null) return null;
  if (speechModule) return speechModule;
  try {
    speechModule = require("expo-speech") as SpeechModule;
    return speechModule;
  } catch {
    speechModule = null;
    return null;
  }
}

export type SpeakResult = { ok: true } | { ok: false; reason: "unavailable" | "error" };

/** Device TTS today; swap for Whisper scoring / pronunciation_url when wired. */
export async function speakWord(
  word: string,
  options?: { language?: string; pronunciationUrl?: string | null },
): Promise<SpeakResult> {
  return speakPlainText(word, options?.language);
}

/** Read aloud assistant text (markdown stripped). */
export async function speakPlainText(
  text: string,
  language = "en-US",
): Promise<SpeakResult> {
  const plain = markdownToPlainText(text);
  if (!plain) return { ok: false, reason: "error" };

  const Speech = loadSpeech();
  if (!Speech) return { ok: false, reason: "unavailable" };

  try {
    Speech.stop();
    await new Promise<void>((resolve) => {
      Speech.speak(plain.slice(0, 8000), {
        language,
        rate: 0.92,
        onDone: () => resolve(),
        onStopped: () => resolve(),
        onError: () => resolve(),
      });
    });
    return { ok: true };
  } catch {
    speechModule = null;
    return { ok: false, reason: "unavailable" };
  }
}

export function stopSpeaking(): void {
  const Speech = loadSpeech();
  if (!Speech) return;
  try {
    Speech.stop();
  } catch {
    speechModule = null;
  }
}

/** Placeholder for future Whisper-based pronunciation check. */
export async function scorePronunciation(_audioUri: string, _expectedWord: string): Promise<null> {
  return null;
}

export function isSpeechAvailable(): boolean {
  return loadSpeech() !== null;
}
