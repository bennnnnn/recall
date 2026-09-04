import { requireOptionalNativeModule } from "expo-modules-core";
import { Platform } from "react-native";

import { speechApi } from "@/lib/api/speech";
import {
  LIVE_TALK_CONNECT_WARMUP_MS,
  LIVE_TALK_PLAYBACK_TAIL_MS,
  LIVE_TALK_SESSION_READY_FALLBACK_MS,
  isLikelyAssistantEcho,
  liveTalkDataChannelText,
  liveTalkLocalMicEnabled,
  liveTalkShouldCreateResponse,
} from "@/lib/liveTalkLogic";
import { yieldMicToWebRtc } from "@/lib/voiceAudio";
import { realtimeFunctionCalls, runRealtimeFunctionCall } from "@/lib/realtimeTools";
import type { SearchSource } from "@/lib/api/types";

export type RealtimeVoiceEvent =
  | { type: "connected" }
  | { type: "speech_started"; turnId?: string }
  | { type: "speech_stopped" }
  | { type: "response_started" }
  | { type: "user_transcript"; text: string }
  | { type: "assistant_transcript"; text: string; final: boolean }
  | { type: "response_done" }
  | { type: "response_interrupted" }
  | { type: "search_sources"; sources: SearchSource[] }
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

const OPENAI_REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";
const ICE_GATHER_TIMEOUT_MS = 2_500;
const CONNECTION_TIMEOUT_MS = 10_000;
const SDP_EXCHANGE_TIMEOUT_MS = 10_000;
const PLAYBACK_UNMUTE_FALLBACK_MS = 12_000;
const DEBUG_PREFIX = "[LiveTalk/WebRTC]";
const SILENCE_HALLUCINATIONS = new Set([
  "thank you for watching",
  "thanks for watching",
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
 * Never import expo-device: its JS calls requireNativeModule('ExpoDevice')
 * and Metro reports that as a fatal even inside try/catch. Probe the native
 * registry instead; null means this binary was built before expo-device.
 */
function isIosSimulator(): boolean {
  if (Platform.OS !== "ios") return false;
  try {
    const device = requireOptionalNativeModule<{ isDevice?: boolean }>("ExpoDevice");
    if (device && typeof device.isDevice === "boolean") {
      return device.isDevice === false;
    }
  } catch {
    // Missing ExpoDevice must not take down Live Talk.
  }
  return true;
}

/**
 * VoiceProcessing IO can deadlock CoreAudio on the iOS Simulator when
 * expo-audio has also touched the session. Only the Simulator uses the
 * half-duplex workaround; physical iOS/Android devices need AEC for barge-in.
 * If ExpoDevice is not in this binary, use the Simulator path so Live Talk
 * can start until the next native rebuild.
 */
export function webRtcMicConstraints(): {
  echoCancellation: boolean;
  noiseSuppression: boolean;
  autoGainControl: boolean;
} {
  if (isIosSimulator()) {
    return { echoCancellation: false, noiseSuppression: false, autoGainControl: false };
  }
  return { echoCancellation: true, noiseSuppression: true, autoGainControl: true };
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

function isKnownSilenceHallucination(text: string): boolean {
  return SILENCE_HALLUCINATIONS.has(normalizeTranscript(text));
}

function sendRealtimePayload(
  channel: { readyState?: string; send?: (data: string) => void },
  payload: Record<string, unknown>,
) {
  if (channel.readyState !== "open" || typeof channel.send !== "function") return;
  try {
    channel.send(JSON.stringify(payload));
  } catch {
    /* best-effort */
  }
}

function sessionTurnSnapshot(event: Record<string, unknown>): Record<string, unknown> {
  const session = event.session;
  if (!session || typeof session !== "object") return { hasSession: false };
  const root = session as Record<string, unknown>;
  const audio = root.audio;
  let turn: Record<string, unknown> | null = null;
  if (audio && typeof audio === "object") {
    const input = (audio as Record<string, unknown>).input;
    if (input && typeof input === "object") {
      const nested = (input as Record<string, unknown>).turn_detection;
      if (nested && typeof nested === "object") turn = nested as Record<string, unknown>;
    }
  }
  if (!turn && root.turn_detection && typeof root.turn_detection === "object") {
    turn = root.turn_detection as Record<string, unknown>;
  }
  return {
    hasSession: true,
    vad: typeof turn?.type === "string" ? turn.type : null,
    create_response: turn?.create_response ?? null,
    interrupt_response: turn?.interrupt_response ?? null,
  };
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
  if (!webrtc) {
    throw new Error("webrtc_unavailable");
  }

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

  // Mint the short-lived credential while local ICE gathering proceeds. The
  // permanent OpenAI API key stays on Recall's server; only this ek_ token is
  // ever exposed to the app.
  const credentialPromise = speechApi.createRealtimeSession(options.token, {
    chatId: options.chatId,
    bargeIn: webRtcMicConstraints().echoCancellation,
  });

  const pc = new webrtc.RTCPeerConnection({});
  for (const track of localStream.getTracks()) {
    pc.addTrack(track, localStream);
  }

  const dataChannel = pc.createDataChannel("oai-events");
  const remoteAudioTracks = new Set<any>();
  let assistantTranscript = "";
  let lastAssistantText = "";
  let closed = false;
  let callId: string | null = null;
  let connectionSettled = false;
  let resolveConnected: (() => void) | null = null;
  let rejectConnected: ((error: Error) => void) | null = null;
  let userMuted = false;
  let assistantSpeaking = false;
  let suppressCurrentInputTurn = false;
  let sessionReadyForTurns = false;
  let acceptedUserUtterance = false;
  let sawOutputAudioStopped = false;
  const bargeIn = webRtcMicConstraints().echoCancellation;
  let activeInputId = "";
  let activeResponseId: string | null = null;
  let turnEpoch = 0;
  let responseFinished = false;
  let userSpeaking = false;
  let toolCallsThisTurn = 0;
  const completedToolCalls = new Set<string>();
  let micResumeTimer: ReturnType<typeof setTimeout> | null = null;
  let sessionReadyTimer: ReturnType<typeof setTimeout> | null = null;

  const clearMicResumeTimer = () => {
    if (micResumeTimer == null) return;
    clearTimeout(micResumeTimer);
    micResumeTimer = null;
  };

  const unmuteAfterPlayback = (delayMs: number) => {
    clearMicResumeTimer();
    micResumeTimer = setTimeout(() => {
      micResumeTimer = null;
      assistantSpeaking = false;
      syncLocalMicState();
    }, delayMs);
  };

  const dropEchoInput = (reason: string, cancelResponse: boolean) => {
    sendRealtimePayload(dataChannel, { type: "input_audio_buffer.clear" });
    if (cancelResponse) {
      sendRealtimePayload(dataChannel, { type: "response.cancel" });
    }
    debug("dropped-echo-input", { reason, cancelResponse });
  };

  const requestAssistantTurn = (reason: string) => {
    if (
      !liveTalkShouldCreateResponse({
        sessionReadyForTurns,
        assistantSpeaking,
        userMuted,
        acceptedUserUtterance,
      })
    ) {
      return;
    }
    acceptedUserUtterance = false;
    assistantSpeaking = true;
    syncLocalMicState();
    sendRealtimePayload(dataChannel, { type: "response.create" });
    debug("response-create", reason);
  };

  const markSessionReadyForTurns = (reason: string) => {
    if (sessionReadyForTurns) return;
    sessionReadyForTurns = true;
    if (sessionReadyTimer != null) {
      clearTimeout(sessionReadyTimer);
      sessionReadyTimer = null;
    }
    debug("session-ready-for-turns", reason);
  };

  const syncLocalMicState = () => {
    const enabled = liveTalkLocalMicEnabled(userMuted, assistantSpeaking, bargeIn);
    for (const track of localAudioTracks) {
      try {
        track.enabled = enabled;
      } catch {
        /* best-effort */
      }
    }
    debug("microphone-gate", { enabled, userMuted, assistantSpeaking });
  };

  const connectedPromise = new Promise<void>((resolve, reject) => {
    resolveConnected = resolve;
    rejectConnected = reject;
  });

  const settleConnected = () => {
    if (connectionSettled) return;
    connectionSettled = true;
    debug("data-channel-open", {
      ice: String(pc.iceConnectionState),
      peer: String(pc.connectionState),
    });
    resolveConnected?.();
    // Session turn_detection is minted server-side. Do not session.update
    // audio.input here — a nested replace can kill server VAD.
    if (sessionReadyTimer != null) clearTimeout(sessionReadyTimer);
    sessionReadyTimer = setTimeout(() => {
      sessionReadyTimer = null;
      markSessionReadyForTurns("fallback");
    }, LIVE_TALK_SESSION_READY_FALLBACK_MS);
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
    if (closed) return;
    const raw = liveTalkDataChannelText(message.data);
    if (raw == null) return;
    let event: Record<string, unknown>;
    try {
      event = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return;
    }
    const type = typeof event.type === "string" ? event.type : "";
    // Cancellation/transcript events for the interrupted response must not
    // complete or overwrite the next user's turn.
    const response = event.response as { id?: string; status?: string } | undefined;
    const responseId = typeof event.response_id === "string" ? event.response_id : response?.id;
    if (type !== "response.created" && responseId && responseId !== activeResponseId) return;
    debug("event", type);
    if (type === "session.created") {
      debug("session-created", sessionTurnSnapshot(event));
      if (sessionReadyTimer != null) clearTimeout(sessionReadyTimer);
      sessionReadyTimer = setTimeout(() => {
        sessionReadyTimer = null;
        markSessionReadyForTurns("session.created+warmup");
      }, LIVE_TALK_CONNECT_WARMUP_MS);
    }
    if (type === "input_audio_buffer.speech_started") {
      suppressCurrentInputTurn = (!bargeIn && assistantSpeaking) || userMuted || !sessionReadyForTurns;
      if (suppressCurrentInputTurn) {
        acceptedUserUtterance = false;
        dropEchoInput("speech-before-user-turn", false);
        return;
      }
      if (bargeIn && assistantSpeaking) {
        // Server WebRTC VAD cancels and truncates unplayed audio automatically.
        options.onEvent({ type: "response_interrupted" });
        assistantSpeaking = false;
        assistantTranscript = "";
        activeResponseId = null;
        clearMicResumeTimer();
      }
      activeInputId = typeof event.item_id === "string" ? event.item_id : String(Date.now());
      userSpeaking = true;
      turnEpoch += 1;
      toolCallsThisTurn = 0;
      acceptedUserUtterance = true;
      options.onEvent({ type: "speech_started", turnId: activeInputId });
      return;
    }
    if (type === "input_audio_buffer.speech_stopped") {
      userSpeaking = false;
      if (suppressCurrentInputTurn) {
        suppressCurrentInputTurn = false;
        acceptedUserUtterance = false;
        return;
      }
      options.onEvent({ type: "speech_stopped" });
      requestAssistantTurn("speech_stopped");
      return;
    }
    if (type === "response.created") {
      if (bargeIn && userSpeaking) {
        // A response.create can cross the next speech_started in flight.
        // Cancel that old response without clearing the user's new audio.
        sendRealtimePayload(dataChannel, { type: "response.cancel", response_id: response?.id });
        return;
      }
      if (suppressCurrentInputTurn) {
        dropEchoInput("response-before-user-turn", true);
        return;
      }
      activeResponseId = response?.id ?? null;
      responseFinished = false;
      assistantTranscript = "";
      clearMicResumeTimer();
      assistantSpeaking = true;
      acceptedUserUtterance = false;
      sawOutputAudioStopped = false;
      syncLocalMicState();
      if (!bargeIn) sendRealtimePayload(dataChannel, { type: "input_audio_buffer.clear" });
      options.onEvent({ type: "response_started" });
      return;
    }
    if (type === "conversation.item.input_audio_transcription.completed") {
      if (typeof event.item_id === "string" && event.item_id !== activeInputId) return;
      const text = transcriptFromEvent(event);
      const echoSource = lastAssistantText || assistantTranscript;
      if (suppressCurrentInputTurn || (!bargeIn && text && isLikelyAssistantEcho(text, echoSource))) {
        dropEchoInput("echo-transcript", false);
        suppressCurrentInputTurn = false;
        debug("ignored-assistant-echo-transcript", text);
        return;
      }
      if (text && isKnownSilenceHallucination(text)) {
        debug("ignored-silence-hallucination", text);
        return;
      }
      if (text) options.onEvent({ type: "user_transcript", text });
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
      if (finalText.trim()) {
        lastAssistantText = finalText.trim();
        options.onEvent({ type: "assistant_transcript", text: lastAssistantText, final: true });
      }
      return;
    }
    if (type === "output_audio_buffer.stopped" || type === "output_audio_buffer.audio_stopped") {
      sawOutputAudioStopped = true;
      if (bargeIn) {
        assistantSpeaking = false;
        clearMicResumeTimer();
        if (responseFinished) options.onEvent({ type: "response_done" });
        return;
      }
      unmuteAfterPlayback(LIVE_TALK_PLAYBACK_TAIL_MS);
      return;
    }
    if (type === "response.done") {
      const calls = realtimeFunctionCalls(event.response);
      if (calls.length > 0) {
        const epoch = turnEpoch;
        const toolTurnId = activeInputId;
        const fresh = calls.filter((call) => !completedToolCalls.has(call.call_id));
        for (const call of fresh) completedToolCalls.add(call.call_id);
        if (!fresh.length) return;
        void Promise.all(fresh.slice(0, 8).map(async (call) => {
          toolCallsThisTurn += 1;
          const result = toolCallsThisTurn <= 2 && callId && options.chatId
            ? await runRealtimeFunctionCall(call, { token: options.token, chatId: options.chatId, callId, turnId: toolTurnId })
            : { content: "Voice lookup limit reached. Answer from available context and disclose missing facts." };
          if (closed) return;
          sendRealtimePayload(dataChannel, { type: "conversation.item.create", item: {
            type: "function_call_output", call_id: call.call_id,
            output: JSON.stringify(epoch === turnEpoch ? result : { content: "Lookup cancelled by a new user turn." }),
          } });
          if (epoch !== turnEpoch) return;
          if ("sources" in result && result.sources?.length) options.onEvent({ type: "search_sources", sources: result.sources });
        })).then(() => {
          if (!closed && epoch === turnEpoch) sendRealtimePayload(dataChannel, { type: "response.create" });
        });
        return;
      }
      suppressCurrentInputTurn = false;
      responseFinished = true;
      if (!bargeIn) sendRealtimePayload(dataChannel, { type: "input_audio_buffer.clear" });
      if (bargeIn && assistantSpeaking && !sawOutputAudioStopped) {
        // Persist only once playback ends; a user can still interrupt buffered audio.
        clearMicResumeTimer();
        micResumeTimer = setTimeout(() => {
          micResumeTimer = null;
          assistantSpeaking = false;
          if (!closed) options.onEvent({ type: "response_done" });
        }, PLAYBACK_UNMUTE_FALLBACK_MS);
        return;
      }
      // Generation finished; RTP/playout can continue. Do not unmute here.
      if (assistantSpeaking && !sawOutputAudioStopped) {
        unmuteAfterPlayback(PLAYBACK_UNMUTE_FALLBACK_MS);
      }
      options.onEvent({ type: "response_done" });
      return;
    }
    if (type === "error") {
      clearMicResumeTimer();
      assistantSpeaking = false;
      suppressCurrentInputTurn = false;
      acceptedUserUtterance = false;
      syncLocalMicState();
      const rawError = event.error;
      const messageText =
        rawError && typeof rawError === "object" && "message" in rawError
          ? String((rawError as { message?: unknown }).message || "Realtime voice failed")
          : "Realtime voice failed";
      emitError(messageText);
    }
  };

  const tearDownAudio = () => {
    clearMicResumeTimer();
    if (sessionReadyTimer != null) {
      clearTimeout(sessionReadyTimer);
      sessionReadyTimer = null;
    }
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
    // iOS Simulator SIGABRTs in AURemoteIO when setRemoteDescription is
    // applied after ICE gathering (candidates in the offer). Trickle from
    // the answer is enough; ICE still reaches connected without them.
    if (Platform.OS !== "ios") {
      await waitForIceGathering(pc);
    }
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
      turnEpoch += 1;
      sendRealtimePayload(dataChannel, { type: "response.cancel" });
      if (bargeIn) sendRealtimePayload(dataChannel, { type: "output_audio_buffer.clear" });
      if (assistantSpeaking) options.onEvent({ type: "response_interrupted" });
      activeResponseId = null;
      assistantSpeaking = false;
      clearMicResumeTimer();
      syncLocalMicState();
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
