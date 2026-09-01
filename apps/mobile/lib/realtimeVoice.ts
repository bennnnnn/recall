import { Platform } from "react-native";

import { speechApi } from "@/lib/api/speech";
import { liveTalkDataChannelText } from "@/lib/liveTalkLogic";
import { yieldMicToWebRtc } from "@/lib/voiceAudio";

export type RealtimeVoiceEvent =
  | { type: "connected" }
  | { type: "speech_started" }
  | { type: "speech_stopped" }
  | { type: "response_started" }
  | { type: "user_transcript"; text: string }
  | { type: "assistant_transcript"; text: string; final: boolean }
  | { type: "response_done" }
  | { type: "error"; message: string };

type NativeWebRtc = {
  __WEBRTC_STUB__?: boolean;
  mediaDevices: {
    getUserMedia: (constraints: object) => Promise<any>;
  };
  RTCPeerConnection: new (config?: object) => any;
  RTCSessionDescription: new (init: { type: string; sdp: string }) => any;
};

export type RealtimeVoiceSession = {
  callId: string | null;
  setMuted: (muted: boolean) => void;
  cancelResponse: () => void;
  close: () => void;
};

type InputTurnState = {
  itemId: string;
  audioStartMs: number | null;
  audioEndMs: number | null;
  suppressed: boolean;
};

export type RealtimeTranscriptGateInput = {
  text: string;
  suppressed: boolean;
  vadDurationMs?: number | null;
  averageLogprob?: number | null;
  recentAssistantText?: string;
  nearAssistantPlayback?: boolean;
};

const OPENAI_REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";
const ICE_GATHER_TIMEOUT_MS = 2_500;
const CONNECTION_TIMEOUT_MS = 10_000;
const SDP_EXCHANGE_TIMEOUT_MS = 10_000;
const POST_PLAYBACK_GUARD_MS = 300;
const VAD_CONFIGURED_PADDING_MS = 900; // 300ms prefix + 600ms trailing silence.
const MIN_EFFECTIVE_SPEECH_MS = 100;
const VERY_LOW_TRANSCRIPT_LOGPROB = -3.5;
const DEBUG_PREFIX = "[LiveTalk/WebRTC]";
const SILENCE_HALLUCINATIONS = new Set([
  "thank you for watching",
  "thanks for watching",
  "thank you for listening",
  "thanks for listening",
  "please subscribe",
  "subscribe",
]);

function debug(stage: string, detail?: unknown): void {
  if (!__DEV__) return;
  if (detail === undefined) {
    console.info(`${DEBUG_PREFIX} ${stage}`);
  } else {
    console.info(`${DEBUG_PREFIX} ${stage}`, detail);
  }
}

function loadWebRtc(): NativeWebRtc | null {
  try {
    // Native module: Live Talk requires a rebuilt dev client, not Expo Go.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const webrtc = require("react-native-webrtc") as NativeWebRtc;
    if (webrtc.__WEBRTC_STUB__) return null;
    return webrtc;
  } catch {
    return null;
  }
}

export function isRealtimeVoiceAvailable(): boolean {
  return loadWebRtc() !== null;
}

/**
 * VoiceProcessing IO can deadlock CoreAudio on the iOS Simulator when
 * expo-audio has also touched the session. Keep the existing iOS-safe capture
 * constraints. Turn authorization is handled above WebRTC, so even if the iOS
 * mic hears speaker output, that echo cannot create a model response.
 */
export function webRtcMicConstraints(): {
  echoCancellation: boolean;
  noiseSuppression: boolean;
  autoGainControl: boolean;
} {
  if (Platform.OS === "ios") {
    return { echoCancellation: false, noiseSuppression: false, autoGainControl: false };
  }
  return { echoCancellation: true, noiseSuppression: true, autoGainControl: true };
}

function stringField(event: Record<string, unknown>, key: string): string {
  const value = event[key];
  return typeof value === "string" ? value : "";
}

function numberField(event: Record<string, unknown>, key: string): number | null {
  const value = event[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function transcriptFromEvent(event: Record<string, unknown>): string {
  const transcript = event.transcript;
  if (typeof transcript === "string") return transcript.trim();
  const delta = event.delta;
  if (typeof delta === "string") return delta;
  return "";
}

function normalizeTranscript(text: string): string {
  return text
    .toLowerCase()
    .replace(/[.!?,;:'"()[\]{}]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function averageTranscriptLogprob(event: Record<string, unknown>): number | null {
  const raw = event.logprobs;
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const values: number[] = [];
  for (const row of raw) {
    if (!row || typeof row !== "object" || !("logprob" in row)) continue;
    const value = (row as { logprob?: unknown }).logprob;
    if (typeof value === "number" && Number.isFinite(value)) values.push(value);
  }
  if (values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function likelyAssistantEcho(text: string, assistantText: string): boolean {
  const input = normalizeTranscript(text);
  const assistant = normalizeTranscript(assistantText);
  if (!input || !assistant) return false;
  if (input.length >= 2 && assistant.includes(input)) return true;
  if (assistant.length >= 8 && input.includes(assistant)) return true;
  return false;
}

/**
 * Returns a stable diagnostic reason when an input transcript must not become
 * a user turn. Keep this intentionally conservative so accented/short genuine
 * speech is accepted while speaker echo and obvious silence hallucinations are
 * rejected.
 */
export function realtimeTranscriptRejectionReason(
  input: RealtimeTranscriptGateInput,
): string | null {
  const normalized = normalizeTranscript(input.text);
  if (input.suppressed) return "assistant_playback";
  if (!normalized) return "empty";
  if (SILENCE_HALLUCINATIONS.has(normalized)) return "known_silence_hallucination";

  if (
    input.nearAssistantPlayback &&
    input.recentAssistantText &&
    likelyAssistantEcho(input.text, input.recentAssistantText)
  ) {
    return "assistant_echo";
  }

  if (input.vadDurationMs != null) {
    const effectiveSpeechMs = Math.max(0, input.vadDurationMs - VAD_CONFIGURED_PADDING_MS);
    if (effectiveSpeechMs < MIN_EFFECTIVE_SPEECH_MS && normalized.length <= 12) {
      return "vad_impulse";
    }
  }

  if (input.averageLogprob != null && input.averageLogprob < VERY_LOW_TRANSCRIPT_LOGPROB) {
    return "very_low_confidence";
  }
  return null;
}

function sendRealtimeJson(
  channel: { readyState?: string; send?: (data: string) => void },
  payload: Record<string, unknown>,
): boolean {
  if (channel.readyState !== "open" || typeof channel.send !== "function") return false;
  try {
    channel.send(JSON.stringify(payload));
    return true;
  } catch {
    return false;
  }
}

function sendRealtimeEvent(
  channel: { readyState?: string; send?: (data: string) => void },
  type: string,
): boolean {
  return sendRealtimeJson(channel, { type });
}

async function waitForIceGathering(pc: any): Promise<void> {
  if (pc.iceGatheringState === "complete") return;
  await new Promise<void>((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try {
        pc.removeEventListener?.("icegatheringstatechange", onStateChange);
      } catch {
        /* best-effort */
      }
      resolve();
    };
    const onStateChange = () => {
      debug("ice-gathering", pc.iceGatheringState);
      if (pc.iceGatheringState === "complete") finish();
    };
    const timer = setTimeout(finish, ICE_GATHER_TIMEOUT_MS);
    pc.addEventListener?.("icegatheringstatechange", onStateChange);
  });
}

function enableRemoteAudioTrack(track: any): void {
  if (!track || track.kind !== "audio") return;
  try {
    track.enabled = true;
  } catch {
    /* remote audio is still auto-rendered by react-native-webrtc */
  }
  try {
    if (typeof track._setVolume === "function") track._setVolume(1);
  } catch {
    /* best-effort */
  }
}

async function exchangeSdpDirectly(clientSecret: string, sdp: string): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), SDP_EXCHANGE_TIMEOUT_MS);
  try {
    const response = await fetch(OPENAI_REALTIME_CALLS_URL, {
      method: "POST",
      body: sdp,
      headers: {
        Authorization: `Bearer ${clientSecret}`,
        "Content-Type": "application/sdp",
      },
      signal: controller.signal,
    });
    const answerSdp = await response.text();
    if (!response.ok) {
      const error = new Error(
        `OpenAI Realtime SDP exchange failed (${response.status}): ${answerSdp.slice(0, 240)}`,
      ) as Error & { status?: number };
      error.status = response.status;
      throw error;
    }
    if (!answerSdp.includes("v=0")) {
      throw new Error("OpenAI Realtime returned an invalid SDP answer");
    }
    return answerSdp;
  } finally {
    clearTimeout(timeout);
  }
}

export async function createRealtimeVoiceSession(options: {
  token: string;
  chatId?: string | null;
  onEvent: (event: RealtimeVoiceEvent) => void;
}): Promise<RealtimeVoiceSession> {
  const webrtc = loadWebRtc();
  if (!webrtc) throw new Error("webrtc_unavailable");

  await yieldMicToWebRtc();
  debug("requesting-microphone", { platform: Platform.OS });
  const localStream = await webrtc.mediaDevices.getUserMedia({
    audio: webRtcMicConstraints(),
    video: false,
  });
  const localAudioTracks = localStream.getAudioTracks();
  if (localAudioTracks.length === 0) {
    for (const track of localStream.getTracks()) track.stop();
    throw new Error("webrtc_unavailable");
  }
  debug("microphone-ready", {
    tracks: localAudioTracks.length,
    enabled: localAudioTracks.map((track: any) => track.enabled),
    readyState: localAudioTracks.map((track: any) => track.readyState),
  });

  const credentialPromise = speechApi.createRealtimeSession(options.token, {
    chatId: options.chatId,
  });

  const pc = new webrtc.RTCPeerConnection({});
  for (const track of localStream.getTracks()) pc.addTrack(track, localStream);

  const dataChannel = pc.createDataChannel("oai-events");
  const remoteAudioTracks = new Set<any>();
  const inputTurns = new Map<string, InputTurnState>();
  const respondedInputItems = new Set<string>();

  let assistantTranscript = "";
  let lastAssistantTranscript = "";
  let closed = false;
  let callId: string | null = null;
  let connectionSettled = false;
  let resolveConnected: (() => void) | null = null;
  let rejectConnected: ((error: Error) => void) | null = null;
  let userMuted = false;
  let responseRequestPending = false;
  let responseActive = false;
  let responseServerDone = false;
  let responseCompletionEmitted = false;
  let assistantPlaybackActive = false;
  let postPlaybackGuardUntil = 0;
  let postPlaybackTimer: ReturnType<typeof setTimeout> | null = null;
  let cancelNextResponse = false;

  const clearPostPlaybackTimer = () => {
    if (postPlaybackTimer == null) return;
    clearTimeout(postPlaybackTimer);
    postPlaybackTimer = null;
  };

  const playbackBlocked = () =>
    assistantPlaybackActive || Date.now() < postPlaybackGuardUntil;

  const turnBlocked = () =>
    responseRequestPending || responseActive || playbackBlocked();

  const syncLocalMicState = () => {
    // On Android, physically close capture while assistant audio is playing.
    // On iOS Simulator, toggling the capture track can destabilize CoreAudio,
    // so the track stays live and manual turn authorization drops its echo.
    const enabled = !userMuted && (Platform.OS === "ios" || !playbackBlocked());
    for (const track of localAudioTracks) {
      try {
        track.enabled = enabled;
      } catch {
        /* best-effort */
      }
    }
    debug("microphone-gate", {
      enabled,
      userMuted,
      assistantPlaybackActive,
      turnAuthorization: "manual",
    });
  };

  const connectedPromise = new Promise<void>((resolve, reject) => {
    resolveConnected = resolve;
    rejectConnected = reject;
  });

  const settleConnected = () => {
    if (connectionSettled) return;
    connectionSettled = true;
    debug("data-channel-open", { turnAuthorization: "manual" });
    resolveConnected?.();
    options.onEvent({ type: "connected" });
  };

  const failConnection = (message: string) => {
    if (connectionSettled) return;
    connectionSettled = true;
    debug("connection-failed", message);
    rejectConnected?.(new Error(message));
  };

  const emitError = (message: string) => {
    debug("realtime-error", message);
    if (!closed) options.onEvent({ type: "error", message });
  };

  const deleteInputItem = (itemId: string, reason: string) => {
    if (!itemId) return;
    debug("deleting-input-item", { itemId, reason });
    sendRealtimeJson(dataChannel, {
      type: "conversation.item.delete",
      item_id: itemId,
    });
    inputTurns.delete(itemId);
  };

  const emitResponseDoneOnce = () => {
    if (responseCompletionEmitted) return;
    responseCompletionEmitted = true;
    options.onEvent({ type: "response_done" });
  };

  const beginPostPlaybackGuard = () => {
    clearPostPlaybackTimer();
    postPlaybackGuardUntil = Date.now() + POST_PLAYBACK_GUARD_MS;
    syncLocalMicState();
    postPlaybackTimer = setTimeout(() => {
      postPlaybackTimer = null;
      postPlaybackGuardUntil = 0;
      syncLocalMicState();
    }, POST_PLAYBACK_GUARD_MS);
  };

  pc.ontrack = (event: { track?: any; streams?: any[] }) => {
    if (event.track?.kind === "audio") {
      remoteAudioTracks.add(event.track);
      enableRemoteAudioTrack(event.track);
      debug("remote-audio-track", {
        id: event.track.id,
        enabled: event.track.enabled,
        muted: event.track.muted,
        readyState: event.track.readyState,
      });
    }
    for (const stream of event.streams ?? []) {
      for (const track of stream.getAudioTracks?.() ?? []) {
        remoteAudioTracks.add(track);
        enableRemoteAudioTrack(track);
      }
    }
  };

  pc.onconnectionstatechange = () => {
    debug("peer-state", pc.connectionState);
    if (pc.connectionState === "failed" || pc.connectionState === "closed") {
      failConnection("Realtime voice connection failed");
      if (!closed) emitError("Realtime voice connection failed");
    }
  };
  pc.oniceconnectionstatechange = () => {
    debug("ice-state", pc.iceConnectionState);
    if (pc.iceConnectionState === "failed") {
      failConnection("Realtime voice ICE connection failed");
      if (!closed) emitError("Realtime voice ICE connection failed");
    }
  };

  dataChannel.onopen = settleConnected;
  dataChannel.onclose = () => debug("data-channel-close");
  dataChannel.onerror = () => {
    failConnection("Realtime voice data channel failed");
    emitError("Realtime voice data channel failed");
  };
  dataChannel.onmessage = (message: { data?: unknown }) => {
    const raw = liveTalkDataChannelText(message.data);
    if (raw == null) return;
    let event: Record<string, unknown>;
    try {
      event = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return;
    }

    const type = stringField(event, "type");
    if (
      type === "session.created" ||
      type === "session.updated" ||
      type === "input_audio_buffer.speech_started" ||
      type === "input_audio_buffer.speech_stopped" ||
      type === "input_audio_buffer.committed" ||
      type === "conversation.item.input_audio_transcription.completed" ||
      type === "conversation.item.input_audio_transcription.failed" ||
      type === "response.created" ||
      type === "response.done" ||
      type === "output_audio_buffer.started" ||
      type === "output_audio_buffer.stopped" ||
      type === "output_audio_buffer.cleared" ||
      type === "error"
    ) {
      debug("event", type);
    }

    if (type === "input_audio_buffer.speech_started") {
      const itemId = stringField(event, "item_id");
      const suppressed = turnBlocked();
      inputTurns.set(itemId, {
        itemId,
        audioStartMs: numberField(event, "audio_start_ms"),
        audioEndMs: null,
        suppressed,
      });
      if (suppressed) {
        debug("suppressed-speech-start", {
          itemId,
          responseRequestPending,
          responseActive,
          assistantPlaybackActive,
        });
        return;
      }
      options.onEvent({ type: "speech_started" });
      return;
    }

    if (type === "input_audio_buffer.speech_stopped") {
      const itemId = stringField(event, "item_id");
      const existing = inputTurns.get(itemId);
      const state: InputTurnState = existing ?? {
        itemId,
        audioStartMs: null,
        audioEndMs: null,
        suppressed: turnBlocked(),
      };
      state.audioEndMs = numberField(event, "audio_end_ms");
      state.suppressed = state.suppressed || turnBlocked();
      inputTurns.set(itemId, state);
      if (!state.suppressed) options.onEvent({ type: "speech_stopped" });
      return;
    }

    if (type === "input_audio_buffer.committed") {
      const itemId = stringField(event, "item_id");
      if (itemId && !inputTurns.has(itemId)) {
        inputTurns.set(itemId, {
          itemId,
          audioStartMs: null,
          audioEndMs: null,
          suppressed: turnBlocked(),
        });
      }
      return;
    }

    if (type === "conversation.item.input_audio_transcription.completed") {
      const itemId = stringField(event, "item_id");
      const text = transcriptFromEvent(event);
      const state = inputTurns.get(itemId);
      const vadDurationMs =
        state?.audioStartMs != null && state.audioEndMs != null
          ? Math.max(0, state.audioEndMs - state.audioStartMs)
          : null;
      const averageLogprob = averageTranscriptLogprob(event);
      const nearAssistantPlayback =
        Boolean(state?.suppressed) || playbackBlocked() || responseActive || responseRequestPending;
      const reason = realtimeTranscriptRejectionReason({
        text,
        suppressed: Boolean(state?.suppressed),
        vadDurationMs,
        averageLogprob,
        recentAssistantText: lastAssistantTranscript || assistantTranscript,
        nearAssistantPlayback,
      });

      if (reason) {
        debug("rejected-user-transcript", {
          itemId,
          reason,
          text,
          vadDurationMs,
          averageLogprob,
        });
        deleteInputItem(itemId, reason);
        return;
      }

      if (!itemId || respondedInputItems.has(itemId)) return;
      if (turnBlocked()) {
        // This can only happen if a second committed turn races the first.
        // Do not let it silently enter model context; the user can repeat it
        // after the current answer finishes.
        deleteInputItem(itemId, "response_in_flight");
        return;
      }

      respondedInputItems.add(itemId);
      inputTurns.delete(itemId);
      options.onEvent({ type: "user_transcript", text });
      responseRequestPending = true;
      responseServerDone = false;
      responseCompletionEmitted = false;
      cancelNextResponse = false;
      const sent = sendRealtimeEvent(dataChannel, "response.create");
      debug("response-requested", { itemId, sent });
      if (!sent) {
        responseRequestPending = false;
        emitError("Could not request realtime voice response");
      }
      return;
    }

    if (type === "conversation.item.input_audio_transcription.failed") {
      const itemId = stringField(event, "item_id");
      deleteInputItem(itemId, "transcription_failed");
      return;
    }

    if (type === "response.created") {
      responseRequestPending = false;
      responseActive = true;
      responseServerDone = false;
      responseCompletionEmitted = false;
      assistantTranscript = "";
      if (cancelNextResponse) {
        cancelNextResponse = false;
        sendRealtimeEvent(dataChannel, "response.cancel");
        sendRealtimeEvent(dataChannel, "output_audio_buffer.clear");
        return;
      }
      options.onEvent({ type: "response_started" });
      return;
    }

    if (type === "output_audio_buffer.started") {
      assistantPlaybackActive = true;
      postPlaybackGuardUntil = 0;
      clearPostPlaybackTimer();
      syncLocalMicState();
      debug("assistant-playback-started", {
        responseId: stringField(event, "response_id"),
      });
      return;
    }

    if (
      type === "response.output_audio_transcript.delta" ||
      type === "response.audio_transcript.delta"
    ) {
      const delta = transcriptFromEvent(event);
      if (!delta) return;
      assistantTranscript += delta;
      options.onEvent({
        type: "assistant_transcript",
        text: assistantTranscript.trimStart(),
        final: false,
      });
      return;
    }

    if (
      type === "response.output_audio_transcript.done" ||
      type === "response.audio_transcript.done"
    ) {
      const finalText = transcriptFromEvent(event) || assistantTranscript;
      assistantTranscript = finalText;
      lastAssistantTranscript = finalText.trim();
      if (lastAssistantTranscript) {
        options.onEvent({
          type: "assistant_transcript",
          text: lastAssistantTranscript,
          final: true,
        });
      }
      return;
    }

    if (type === "response.done") {
      responseRequestPending = false;
      responseActive = false;
      responseServerDone = true;
      // response.done is generation completion, not playback completion. For
      // WebRTC, wait for output_audio_buffer.stopped before finishing the turn.
      if (!assistantPlaybackActive) emitResponseDoneOnce();
      return;
    }

    if (type === "output_audio_buffer.stopped" || type === "output_audio_buffer.cleared") {
      assistantPlaybackActive = false;
      beginPostPlaybackGuard();
      debug("assistant-playback-stopped", {
        responseId: stringField(event, "response_id"),
        serverDone: responseServerDone,
      });
      if (responseServerDone) emitResponseDoneOnce();
      return;
    }

    if (type === "error") {
      responseRequestPending = false;
      const rawError = event.error;
      const messageText =
        rawError && typeof rawError === "object" && "message" in rawError
          ? String((rawError as { message?: unknown }).message || "Realtime voice failed")
          : "Realtime voice failed";
      emitError(messageText);
    }
  };

  const tearDownAudio = () => {
    clearPostPlaybackTimer();
    for (const track of remoteAudioTracks) {
      try {
        track.enabled = false;
      } catch {
        /* best-effort */
      }
    }
    remoteAudioTracks.clear();
    for (const track of localStream.getTracks()) track.stop();
    pc.close();
  };

  try {
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    // iOS Simulator can crash CoreAudio when applying an offer after local ICE
    // candidates are gathered. Keep the existing iOS trickle behavior.
    if (Platform.OS !== "ios") await waitForIceGathering(pc);
    const offerSdp = String(offer.sdp || "");
    const localSdp = String(pc.localDescription?.sdp || "");
    const sdp = offerSdp || localSdp;
    if (!sdp) throw new Error("Could not create realtime audio offer");
    debug("sending-sdp", {
      transport: "direct-ephemeral",
      hasAudio: sdp.includes("m=audio"),
      hasData: sdp.includes("m=application"),
      hasCandidate: sdp.includes("a=candidate"),
      gathering: pc.iceGatheringState,
      turnAuthorization: "manual",
    });

    const credential = await credentialPromise;
    callId = credential.call_id;
    debug("client-secret-ready", {
      model: credential.model,
      expiresAt: credential.expires_at,
    });

    const answerSdp = await exchangeSdpDirectly(credential.client_secret, sdp);
    debug("received-sdp-answer", {
      transport: "direct-ephemeral",
      hasAudio: answerSdp.includes("m=audio"),
      hasData: answerSdp.includes("m=application"),
    });
    await pc.setRemoteDescription(
      new webrtc.RTCSessionDescription({ type: "answer", sdp: answerSdp }),
    );

    for (const receiver of pc.getReceivers?.() ?? []) {
      if (receiver.track?.kind === "audio") {
        remoteAudioTracks.add(receiver.track);
        enableRemoteAudioTrack(receiver.track);
      }
    }

    await Promise.race([
      connectedPromise,
      new Promise<never>((_, reject) =>
        setTimeout(
          () => reject(new Error("Realtime voice connection timed out")),
          CONNECTION_TIMEOUT_MS,
        ),
      ),
    ]);
  } catch (error) {
    closed = true;
    tearDownAudio();
    try {
      dataChannel.close();
    } catch {
      /* best-effort */
    }
    throw error;
  }

  return {
    callId,
    setMuted: (muted: boolean) => {
      userMuted = muted;
      syncLocalMicState();
    },
    cancelResponse: () => {
      if (responseRequestPending && !responseActive) {
        cancelNextResponse = true;
        return;
      }
      if (responseActive || assistantPlaybackActive) {
        sendRealtimeEvent(dataChannel, "response.cancel");
        sendRealtimeEvent(dataChannel, "output_audio_buffer.clear");
      }
    },
    close: () => {
      if (closed) return;
      closed = true;
      debug("closing-session");
      try {
        dataChannel.close();
      } catch {
        /* best-effort */
      }
      tearDownAudio();
    },
  };
}
