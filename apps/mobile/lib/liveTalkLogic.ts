export type LiveTalkPhase = "idle" | "recording" | "thinking" | "speaking" | "paused";

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
export type LiveTalkSpeakerAction = "pause" | "resume";

/** Orb tap: start/stop a listen or cancel a wait. Pause is the speaker, not the orb. */
export function liveTalkOrbAction(phase: LiveTalkPhase): LiveTalkOrbAction {
  if (phase === "thinking") return "cancelThink";
  if (phase === "speaking" || phase === "paused") return "none";
  if (phase === "recording") return "finishListen";
  return "begin";
}

/** Speaker control: pause/resume playback. Hidden unless audio is up. */
export function liveTalkSpeakerAction(phase: LiveTalkPhase): LiveTalkSpeakerAction | null {
  if (phase === "speaking") return "pause";
  if (phase === "paused") return "resume";
  return null;
}

/** Speak control: cut playback and take the floor. Not full duplex. */
export function liveTalkCanTakeFloor(phase: LiveTalkPhase): boolean {
  return phase === "speaking" || phase === "paused";
}

export function liveTalkHintKey(
  phase: LiveTalkPhase,
):
  | "chat.live_talk_listening"
  | "chat.live_talk_thinking"
  | "chat.live_talk_speaking"
  | "chat.live_talk_paused"
  | "chat.live_talk_tap" {
  if (phase === "recording") return "chat.live_talk_listening";
  if (phase === "thinking") return "chat.live_talk_thinking";
  if (phase === "speaking") return "chat.live_talk_speaking";
  if (phase === "paused") return "chat.live_talk_paused";
  return "chat.live_talk_tap";
}

export function liveTalkOrbA11yKey(
  phase: LiveTalkPhase,
): "chat.live_talk_cancel_a11y" | "chat.live_talk_a11y" {
  if (phase === "thinking") return "chat.live_talk_cancel_a11y";
  return "chat.live_talk_a11y";
}

export function liveTalkSpeakerA11yKey(
  phase: LiveTalkPhase,
): "chat.live_talk_pause_a11y" | "chat.live_talk_resume_a11y" | null {
  if (phase === "speaking") return "chat.live_talk_pause_a11y";
  if (phase === "paused") return "chat.live_talk_resume_a11y";
  return null;
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
