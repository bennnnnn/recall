/** Device TTS via expo-speech; Whisper/pronunciation_url later. */

type SpeechModule = typeof import("expo-speech");

let speechModule: SpeechModule | null = null;
let speechLoadAttempted = false;
let speechUnavailable = false;

async function loadSpeech(): Promise<SpeechModule | null> {
  if (speechUnavailable) return null;
  if (speechModule) return speechModule;
  if (speechLoadAttempted) return null;
  speechLoadAttempted = true;
  try {
    speechModule = await import("expo-speech");
    return speechModule;
  } catch {
    speechUnavailable = true;
    return null;
  }
}

export type SpeakResult = { ok: true } | { ok: false; reason: "unavailable" | "error" };

/** Device TTS today; swap for Whisper scoring / pronunciation_url when wired. */
export async function speakWord(
  word: string,
  options?: { language?: string; pronunciationUrl?: string | null },
): Promise<SpeakResult> {
  const text = word.trim();
  if (!text) return { ok: false, reason: "error" };

  // Future: play pronunciationUrl or run Whisper scoring pipeline.
  if (options?.pronunciationUrl) {
    // Reserved for pre-generated audio from backend.
  }

  const Speech = await loadSpeech();
  if (!Speech) return { ok: false, reason: "unavailable" };

  try {
    Speech.stop();
    await new Promise<void>((resolve) => {
      Speech.speak(text, {
        language: options?.language ?? "en-US",
        rate: 0.9,
        onDone: () => resolve(),
        onStopped: () => resolve(),
        onError: () => resolve(),
      });
    });
    return { ok: true };
  } catch {
    speechUnavailable = true;
    return { ok: false, reason: "unavailable" };
  }
}

export function stopSpeaking(): void {
  if (!speechModule || speechUnavailable) return;
  try {
    speechModule.stop();
  } catch {
    speechUnavailable = true;
  }
}

/** Placeholder for future Whisper-based pronunciation check. */
export async function scorePronunciation(_audioUri: string, _expectedWord: string): Promise<null> {
  return null;
}

export function isSpeechAvailable(): boolean {
  return !speechUnavailable && speechModule !== null;
}
