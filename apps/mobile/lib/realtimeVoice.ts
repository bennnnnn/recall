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

const OPENAI_REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";
const ICE_GATHER_TIMEOUT_MS = 2_500;
const CONNECTION_TIMEOUT_MS = 10_000;
const SDP_EXCHANGE_TIMEOUT_MS = 10_000;
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
 * VoiceProcessing IO can deadlock CoreAudio on the iOS Simulator when
 * expo-audio has also touched the session. Keep processing on Android; on iOS
 * the transport runs half-duplex while assistant audio is playing, so speaker
 * echo cannot feed back into the model even without VoiceProcessing IO.
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

function sendRealtimeEvent(
  channel: { readyState?: string; send?: (data: string) => void },
  type: string,
) {
  if (channel.readyState !== "open" || typeof channel.send !== "function") return;
  try {
    channel.send(JSON.stringify({ type }));
  } catch {
    /* best-effort */
  }
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
  });

  const pc = new webrtc.RTCPeerConnection({});
  for (const track of localStream.getTracks()) {
    pc.addTrack(track, localStream);
  }

  const dataChannel = pc.createDataChannel("oai-events");
  const remoteAudioTracks = new Set<any>();
  let assistantTranscript = "";
  let closed = false;
  let callId: string | null = null;
  let connectionSettled = false;
  let resolveConnected: (() => void) | null = null;
  let rejectConnected: ((error: Error) => void) | null = null;
  let userMuted = false;
  let assistantSpeaking = false;
  let suppressCurrentInputTurn = false;

  const syncLocalMicState = () => {
    const enabled = !userMuted && !assistantSpeaking;
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
    debug("data-channel-open");
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
    const type = typeof event.type === "string" ? event.type : "";
    if (
      type === "session.created" ||
      type === "session.updated" ||
      type === "input_audio_buffer.speech_started" ||
      type === "input_audio_buffer.speech_stopped" ||
      type === "response.created" ||
      type === "response.done" ||
      type === "error"
    ) {
      debug("event", type);
    }
    if (type === "input_audio_buffer.speech_started") {
      // A speech event that races with assistant playback is almost always
      // residual speaker echo. Ignore it rather than creating a second turn.
      suppressCurrentInputTurn = assistantSpeaking;
      if (suppressCurrentInputTurn) {
        debug("ignored-input-during-assistant");
        return;
      }
      options.onEvent({ type: "speech_started" });
      return;
    }
    if (type === "input_audio_buffer.speech_stopped") {
      if (suppressCurrentInputTurn) return;
      options.onEvent({ type: "speech_stopped" });
      return;
    }
    if (type === "response.created") {
      assistantTranscript = "";
      assistantSpeaking = true;
      syncLocalMicState();
      options.onEvent({ type: "response_started" });
      return;
    }
    if (type === "conversation.item.input_audio_transcription.completed") {
      const text = transcriptFromEvent(event);
      if (suppressCurrentInputTurn) {
        debug("ignored-assistant-echo-transcript", text);
        suppressCurrentInputTurn = false;
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
        options.onEvent({ type: "assistant_transcript", text: finalText.trim(), final: true });
      }
      return;
    }
    if (type === "response.done") {
      assistantSpeaking = false;
      suppressCurrentInputTurn = false;
      syncLocalMicState();
      options.onEvent({ type: "response_done" });
      return;
    }
    if (type === "error") {
      assistantSpeaking = false;
      suppressCurrentInputTurn = false;
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
    await waitForIceGathering(pc);
    const sdp = String(pc.localDescription?.sdp || offer.sdp || "");
    if (!sdp) throw new Error("Could not create realtime audio offer");
    debug("sending-sdp", {
      transport: "direct-ephemeral",
      hasAudio: sdp.includes("m=audio"),
      hasData: sdp.includes("m=application"),
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
    cancelResponse: () => sendRealtimeEvent(dataChannel, "response.cancel"),
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
