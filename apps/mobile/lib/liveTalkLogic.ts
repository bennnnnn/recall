export type LiveTalkPhase = "idle" | "recording" | "thinking" | "speaking";

export type LiveTalkGate = "ok" | "upgrade" | "limit" | "unavailable" | "offline";

export type LiveTalkStatus = {
  enabled: boolean;
  entitled: boolean;
  remaining: number;
  limit: number;
  refunded?: boolean;
};

export const LIVE_TALK_SPEECH_LEVEL = 0.32;
export const LIVE_TALK_SILENCE_LEVEL = 0.22;
export const LIVE_TALK_SILENCE_MS = 550;
export const LIVE_TALK_MIN_SPEECH_MS = 400;
/** Pause after playback before the mic opens so the speaker is not captured. */
export const LIVE_TALK_ECHO_GUARD_MS = 250;
/** Hard stop so a quiet room cannot record until the 5MB upload cap. */
export const LIVE_TALK_MAX_RECORDING_MS = 30_000;
/** Stop if the meter never crosses speech level (covered mic, low gain). */
export const LIVE_TALK_NO_SPEECH_MS = 8_000;

export type LiveTalkOrbAction = "begin" | "finishListen" | "cancelThink" | "none";

/** Orb tap: start/stop a listen or cancel a wait. Mute is the mic control, not the orb. */
export function liveTalkOrbAction(phase: LiveTalkPhase): LiveTalkOrbAction {
  if (phase === "thinking") return "cancelThink";
  if (phase === "speaking") return "none";
  if (phase === "recording") return "finishListen";
  return "begin";
}

/** Mute drops an in-flight listen so the model never hears it. Playback keeps going. */
export function liveTalkDiscardListenOnMute(phase: LiveTalkPhase): boolean {
  return phase === "recording" || phase === "thinking";
}

/** Speak control: cut playback and take the floor. Not full duplex. */
export function liveTalkCanTakeFloor(phase: LiveTalkPhase): boolean {
  return phase === "speaking";
}

/** Client abort before the first audio clip must refund the reserved turn. */
export function liveTalkAbortRefundNeeded(gotAudio: boolean): boolean {
  return !gotAudio;
}

export const LIVE_TALK_EMPTY_TRANSCRIPT = "empty_transcript";

export function liveTalkIsEmptyTranscriptError(error: unknown): boolean {
  return error instanceof Error && error.message === LIVE_TALK_EMPTY_TRANSCRIPT;
}

/** Auto-stop without a speech spike must not upload silence as a turn. */
export function liveTalkShouldSendRecording(heardSpeech: boolean): boolean {
  return heardSpeech;
}

export function liveTalkMuteA11yKey(
  muted: boolean,
): "chat.live_talk_mute_a11y" | "chat.live_talk_unmute_a11y" {
  return muted ? "chat.live_talk_unmute_a11y" : "chat.live_talk_mute_a11y";
}

/** Mic + close sit beside an empty composer; typing takes the full row. */
export function liveTalkShowsSideChrome(draft: string): boolean {
  return draft.trim().length === 0;
}

export function liveTalkOrbA11yKey(
  phase: LiveTalkPhase,
): "chat.live_talk_cancel_a11y" | "chat.live_talk_a11y" {
  if (phase === "thinking") return "chat.live_talk_cancel_a11y";
  return "chat.live_talk_a11y";
}

export function liveTalkGate(status: LiveTalkStatus | null, isOffline: boolean): LiveTalkGate {
  if (isOffline) return "offline";
  if (!status || !status.enabled) return "unavailable";
  if (!status.entitled || status.limit <= 0) return "upgrade";
  if (status.remaining <= 0) return "limit";
  return "ok";
}

export function liveTalkErrorGate(error: unknown): LiveTalkGate {
  const status =
    error && typeof error === "object" && "status" in error
      ? (error as { status: unknown }).status
      : undefined;
  if (status === 403) return "upgrade";
  if (status === 429) return "limit";
  if (status === 404 || status === 503) return "unavailable";
  return "unavailable";
}

export function liveTalkSilenceDecision(options: {
  meter: number;
  now: number;
  recordingStartedAt: number;
  heardSpeech: boolean;
  silenceStartedAt: number | null;
}): { heardSpeech: boolean; silenceStartedAt: number | null; shouldStop: boolean } {
  const elapsed = options.now - options.recordingStartedAt;
  if (elapsed >= LIVE_TALK_MAX_RECORDING_MS) {
    return {
      heardSpeech: options.heardSpeech,
      silenceStartedAt: options.silenceStartedAt,
      shouldStop: true,
    };
  }
  if (!options.heardSpeech && elapsed >= LIVE_TALK_NO_SPEECH_MS) {
    return { heardSpeech: false, silenceStartedAt: null, shouldStop: true };
  }
  if (options.meter >= LIVE_TALK_SPEECH_LEVEL) {
    return { heardSpeech: true, silenceStartedAt: null, shouldStop: false };
  }
  if (!options.heardSpeech) {
    return { heardSpeech: false, silenceStartedAt: null, shouldStop: false };
  }
  if (options.now - options.recordingStartedAt < LIVE_TALK_MIN_SPEECH_MS) {
    return { heardSpeech: true, silenceStartedAt: null, shouldStop: false };
  }
  if (options.meter > LIVE_TALK_SILENCE_LEVEL) {
    return { heardSpeech: true, silenceStartedAt: null, shouldStop: false };
  }
  const silenceStartedAt = options.silenceStartedAt ?? options.now;
  return {
    heardSpeech: true,
    silenceStartedAt,
    shouldStop: options.now - silenceStartedAt >= LIVE_TALK_SILENCE_MS,
  };
}
