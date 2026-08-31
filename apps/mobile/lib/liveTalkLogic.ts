export type LiveTalkPhase = "idle" | "recording" | "thinking" | "speaking";

export type LiveTalkGate = "ok" | "upgrade" | "limit" | "unavailable" | "offline" | "unconfigured";

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

/** Client abort before the first audio clip or spoken reply must refund. */
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

/** Keep an in-flight WebRTC session only if this open() is still the current one. */
export function liveTalkShouldAttachSession(startedGen: number, currentGen: number): boolean {
  return startedGen === currentGen;
}

export function liveTalkErrorGate(error: unknown): LiveTalkGate {
  if (error instanceof Error && error.message === "webrtc_unavailable") {
    return "unavailable";
  }
  const status =
    error && typeof error === "object" && "status" in error
      ? (error as { status: unknown }).status
      : undefined;
  if (status === 403) return "upgrade";
  if (status === 429) return "limit";
  if (status === 503) return "unconfigured";
  if (status === 404) return "unavailable";
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

/** Speak a phrase before the stream ends so we do not wait for GPT Audio `done`. */
export const LIVE_TALK_SPEAK_MIN_CHARS = 40;

function isSpokenSentenceEnd(ch: string): boolean {
  return ch === "." || ch === "!" || ch === "?" || ch === "…" || ch === "。";
}

/** Next phrase to speak from a growing assistant transcript. */
export function nextLiveTalkSpeakChunk(
  full: string,
  spokenLen: number,
): { chunk: string; consumed: number } {
  const start = spokenLen < 0 ? 0 : spokenLen;
  if (start >= full.length) return { chunk: "", consumed: start };
  const rest = full.slice(start);
  for (let i = 0; i < rest.length; i += 1) {
    const ch = rest[i] ?? "";
    if (!isSpokenSentenceEnd(ch)) continue;
    const next = rest[i + 1];
    if (next && next !== " " && next !== "\n") continue;
    const raw = rest.slice(0, i + 1);
    const chunk = raw.trim();
    if (chunk) return { chunk, consumed: start + raw.length };
  }
  const trimmed = rest.trim();
  if (trimmed.length >= LIVE_TALK_SPEAK_MIN_CHARS) {
    let cut = -1;
    const from = Math.min(rest.length - 1, 120);
    for (let i = from; i >= 20; i -= 1) {
      if (rest[i] === " ") {
        cut = i;
        break;
      }
    }
    const raw = cut >= 20 ? rest.slice(0, cut) : rest.slice(0, Math.min(rest.length, 80));
    const chunk = raw.trim();
    if (chunk) return { chunk, consumed: start + raw.length };
  }
  return { chunk: "", consumed: start };
}

export function liveTalkSpeakFlush(full: string, spokenLen: number): string {
  if (spokenLen >= full.length) return "";
  return full.slice(Math.max(0, spokenLen)).trim();
}
