/**
 * Settings → Voice: a voice picked says its name ("Hi, I'm Heart."), spoken by the engine
 * that will speak it (`POST /speech/voice-preview`). Each clip is asked for once per voice,
 * kind and app language, kept for the app's run, and played once on each pick.
 */
import { speechApi, type VoicePreviewClip, type VoicePreviewKind } from "@/features/speech/api";
import { playVoicePreview } from "@/features/speech/model/pronunciation";
import { reportFailure } from "@/lib/sentry";

/** The same for every account (a voice saying its name): no account data. */
const clips = new Map<string, VoicePreviewClip>();

function clipKey(kind: VoicePreviewKind, voice: string, locale: string): string {
  return `${kind}:${voice}:${locale}`;
}

/** Say ``voice``'s name in it; best effort (a failure, or no plan for it, plays nothing). */
export async function previewVoice(
  token: string,
  kind: VoicePreviewKind,
  voice: string,
  locale: string,
): Promise<boolean> {
  const key = clipKey(kind, voice, locale);
  try {
    let clip = clips.get(key);
    if (!clip) {
      clip = await speechApi.voicePreview(token, { voice, kind });
      if (!clip?.audio_base64) return false;
      clips.set(key, clip);
    }
    const played = await playVoicePreview(clip.audio_base64, clip.content_type);
    return played.ok;
  } catch (error) {
    reportFailure("voice_preview", error);
    return false;
  }
}

export function resetVoicePreviewsForTest(): void {
  clips.clear();
}
