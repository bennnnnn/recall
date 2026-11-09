/**
 * Settings → Voice → Speed: how fast read-aloud plays, on this device.
 * Live talk speaks at its own pace. Not a secret — a file.
 */
import { createFilePref } from "@/lib/filePrefs";

export const SPEECH_RATES = [0.75, 1, 1.25, 1.5] as const;
export type SpeechRate = (typeof SPEECH_RATES)[number];

export function normalizeSpeechRate(raw: string | number | null | undefined): SpeechRate {
  const value = typeof raw === "number" ? raw : Number.parseFloat(raw ?? "");
  return SPEECH_RATES.find((rate) => rate === value) ?? 1;
}

const ratePref = createFilePref<SpeechRate>("recall.speech-rate.txt", normalizeSpeechRate);

/** The loaded rate; 1 until getSpeechRate has read the file once. */
export function currentSpeechRate(): SpeechRate {
  return ratePref.peek() ?? 1;
}

export const { get: getSpeechRate, set: setSpeechRate, reset: resetSpeechRateForTest } = ratePref;
