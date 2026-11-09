/**
 * Which cloud TTS alias to send to POST /speech/tts. Not a secret — filesystem.
 */
import { createFilePref } from "@/lib/filePrefs";

export const TTS_DEVICE_MODEL = "device";
export const TTS_QUALITY_MODEL = "speech-tts-model";
export const TTS_FAST_MODEL = "speech-tts-fast-model";
type TtsModelAlias =
  | typeof TTS_DEVICE_MODEL
  | typeof TTS_QUALITY_MODEL
  | typeof TTS_FAST_MODEL;

export function normalizeTtsModel(raw: string | null | undefined): TtsModelAlias {
  if (raw === TTS_DEVICE_MODEL) return TTS_DEVICE_MODEL;
  return TTS_QUALITY_MODEL;
}

const ttsModelPref = createFilePref<TtsModelAlias>("recall.tts-model.txt", normalizeTtsModel);

export const { get: getTtsModel, set: setTtsModel, reset: resetTtsModelForTest } = ttsModelPref;
