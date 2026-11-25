import type { User, UserVoice } from "@/lib/api";

/** Settings → Voice → Live talk voice, in the order the menu lists them. Names are not translated. */
export const USER_VOICES: readonly UserVoice[] = [
  "marin",
  "cedar",
  "alloy",
  "ash",
  "ballad",
  "coral",
  "echo",
  "sage",
  "shimmer",
  "verse",
];

export function voiceLabel(voice: UserVoice): string {
  return voice.charAt(0).toUpperCase() + voice.slice(1);
}

type ReplyVoice = { id: string; female: boolean };

/** tts-1's voices: it plays replies in Russian, Turkish and Amharic. */
const OPENAI_REPLY_VOICES: readonly ReplyVoice[] = [
  { id: "coral", female: true },
  { id: "alloy", female: true },
  { id: "nova", female: true },
  { id: "sage", female: true },
  { id: "shimmer", female: true },
  { id: "ash", female: false },
  { id: "echo", female: false },
  { id: "fable", female: false },
  { id: "onyx", female: false },
];

/**
 * Settings → Voice → Reply voice, by app language: the voices of the model that plays a
 * reply in that language (Kokoro for these five, tts-1 for the rest), so the voice picked
 * is the voice heard. The server's `models/voice_catalog.py` holds the same lists; both are
 * held to `docs/fixtures/reply_voices.json`.
 */
export const REPLY_VOICES: Readonly<Record<string, readonly ReplyVoice[]>> = {
  en: [
    { id: "af_heart", female: true },
    { id: "af_bella", female: true },
    { id: "af_nicole", female: true },
    { id: "af_kore", female: true },
    { id: "af_sarah", female: true },
    { id: "bf_emma", female: true },
    { id: "am_michael", female: false },
    { id: "am_fenrir", female: false },
    { id: "am_puck", female: false },
    { id: "bm_george", female: false },
  ],
  es: [
    { id: "ef_dora", female: true },
    { id: "em_alex", female: false },
  ],
  fr: [{ id: "ff_siwis", female: true }],
  hi: [
    { id: "hf_alpha", female: true },
    { id: "hf_beta", female: true },
    { id: "hm_omega", female: false },
    { id: "hm_psi", female: false },
  ],
  pt: [
    { id: "pf_dora", female: true },
    { id: "pm_alex", female: false },
  ],
  ru: OPENAI_REPLY_VOICES,
  tr: OPENAI_REPLY_VOICES,
  am: OPENAI_REPLY_VOICES,
};

/** The Reply voice picker's voices for an app language (English's for one it lacks). */
export function replyVoicesFor(locale: string | null | undefined): readonly ReplyVoice[] {
  const code = (locale ?? "en").trim().toLowerCase().split("-")[0] ?? "en";
  return REPLY_VOICES[code] ?? REPLY_VOICES.en ?? [];
}

/** "af_heart" → "Heart", "coral" → "Coral". Names are not translated. */
export function replyVoiceLabel(id: string): string {
  const name = id.includes("_") ? id.slice(id.indexOf("_") + 1) : id;
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/**
 * The voice the Settings page's Voice row names: the reply voice heard, the one a tap on
 * Listen plays (live talk's is on the Voice page); the live talk voice from an older server;
 * else null.
 */
export function heardVoiceLabel(
  user: Pick<User, "reply_voice_heard" | "tts_voice"> | null | undefined,
): string | null {
  if (user?.reply_voice_heard) return replyVoiceLabel(user.reply_voice_heard);
  return user?.tts_voice ? voiceLabel(user.tts_voice) : null;
}

/**
 * The key of the voices a reply's Listen clips depend on: the reply voice picked and the live
 * talk voice (a reply in another language, or one never picked, follows the live talk voice).
 * A change of either asks for the clips anew. Null when neither is set.
 */
export function listenVoiceKey(
  user: Pick<User, "reply_voice" | "tts_voice"> | null | undefined,
): string | null {
  const picked = user?.reply_voice ?? null;
  const live = user?.tts_voice ?? null;
  return picked || live ? `${picked ?? ""}|${live ?? ""}` : null;
}
