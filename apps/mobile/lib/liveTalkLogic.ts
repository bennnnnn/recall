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
