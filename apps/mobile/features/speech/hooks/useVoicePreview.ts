import { useCallback } from "react";

import { useAuth, useAuthUserReader } from "@/contexts/AuthContext";
import type { VoicePreviewKind } from "@/features/speech/api";
import { previewVoice } from "@/features/speech/model/voicePreview";
import { hasPlanFeature } from "@/lib/plan";

/**
 * Settings → Voice: say the voice just picked ("Hi, I'm Heart."), on a plan that has it (the
 * natural TTS voice, live talk). A TTS pick says the voice a reply will really play in, read
 * after the save: "Same as live talk" says the voice that follows.
 */
export function useVoicePreview(): (kind: VoicePreviewKind, voice?: string | null) => void {
  const { token } = useAuth();
  const readUser = useAuthUserReader();
  return useCallback(
    (kind: VoicePreviewKind, voice?: string | null) => {
      const user = readUser();
      if (!token || !user) return;
      if (!hasPlanFeature(user, kind === "reply" ? "speech_tts" : "live_talk")) return;
      const heard = voice ?? (kind === "reply" ? user.reply_voice_heard : null);
      if (!heard) return;
      void previewVoice(token, kind, heard, user.locale);
    },
    [readUser, token],
  );
}
