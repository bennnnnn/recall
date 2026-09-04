export type LiveTalkPhase = "idle" | "recording" | "thinking" | "speaking";

export type LiveTalkGate = "ok" | "upgrade" | "limit" | "unavailable" | "offline" | "unconfigured";

export type LiveTalkStatus = {
  enabled: boolean;
  entitled: boolean;
  remaining: number;
  limit: number;
  refunded?: boolean;
};

/** Local tail after `output_audio_buffer.stopped` before the mic reopens. */
export const LIVE_TALK_PLAYBACK_TAIL_MS = 500;
/** Ignore connect/track-start noise before the first real user utterance. */
export const LIVE_TALK_CONNECT_WARMUP_MS = 1_500;
/** If session.created never arrives, start accepting user turns after this. */
export const LIVE_TALK_SESSION_READY_FALLBACK_MS = 2_500;

export type LiveTalkOrbAction = "begin" | "finishListen" | "cancelThink" | "none";

export type LiveTalkOrbMode = "listen" | "speak" | "think" | "idle";

/** Visual language for the orb — no on-screen Listening/Speaking copy. */
export function liveTalkOrbMode(phase: LiveTalkPhase): LiveTalkOrbMode {
  if (phase === "recording") return "listen";
  if (phase === "speaking") return "speak";
  if (phase === "thinking") return "think";
  return "idle";
}

/** Orb tap: start/stop a listen or cancel a wait. Mute is the mic control, not the orb. */
export function liveTalkOrbAction(phase: LiveTalkPhase): LiveTalkOrbAction {
  if (phase === "thinking") return "cancelThink";
  if (phase === "speaking") return "none";
  if (phase === "recording") return "finishListen";
  return "begin";
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

/** react-native-webrtc may deliver data-channel payloads as a string or bytes. */
export function liveTalkDataChannelText(data: unknown): string | null {
  if (typeof data === "string") return data;
  if (data instanceof ArrayBuffer) {
    return new TextDecoder().decode(data);
  }
  if (ArrayBuffer.isView(data)) {
    return new TextDecoder().decode(data);
  }
  return null;
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

/** Capture stays off while the assistant is playing so speaker echo cannot VAD. */
export function liveTalkLocalMicEnabled(userMuted: boolean, assistantSpeaking: boolean, bargeIn = false): boolean {
  return !userMuted && (bargeIn || !assistantSpeaking);
}

/** Manual `response.create` only after an accepted user utterance. */
export function liveTalkShouldCreateResponse(input: {
  sessionReadyForTurns: boolean;
  assistantSpeaking: boolean;
  userMuted: boolean;
  acceptedUserUtterance: boolean;
}): boolean {
  return (
    input.sessionReadyForTurns &&
    input.acceptedUserUtterance &&
    !input.assistantSpeaking &&
    !input.userMuted
  );
}

export function liveTalkNormalizeTranscript(text: string): string {
  return text
    .toLowerCase()
    .replace(/[.!?,;:'"()[\]{}]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Speaker bleed often transcribes as a short slice of the last assistant line. */
export function isLikelyAssistantEcho(userText: string, lastAssistantText: string): boolean {
  const user = liveTalkNormalizeTranscript(userText);
  const assistant = liveTalkNormalizeTranscript(lastAssistantText);
  if (!user) return true;
  if (!assistant) return false;
  return assistant.includes(user);
}
