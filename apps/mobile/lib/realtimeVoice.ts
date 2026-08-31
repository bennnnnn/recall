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

const ICE_GATHER_TIMEOUT_MS = 2_500;
const CONNECTION_TIMEOUT_MS = 10_000;
const DEBUG_PREFIX = "[LiveTalk/WebRTC]";

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
    // Metro still extracts this require at bundle time; metro.config.js maps
    // a stub when the package is not installed so chat can still load.
    // Do not gate on NativeModules.WebRTCModule first — New Arch interop can
    // leave that key empty until the JS package loads, which falsely looked
    // like Expo Go on a linked dev client.
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
 * VoiceProcessing IO (AEC) deadlocks CoreAudio on the iOS Simulator when
 * expo-audio has also touched the session — SIGABRT `AURemoteIO RPC timeout`.
 * Keep AEC on Android; iOS uses a plain RemoteIO unit.
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

/**
 * The Realtime calls endpoint is a one-shot SDP exchange; there is no second
 * signalling request for trickled local ICE candidates. React Native WebRTC
 * updates localDescription as gathering progresses, so give it a short window
 * and send the freshest SDP rather than the original createOffer() snapshot.
 */
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
    // react-native-webrtc automatically handles remote audio. Explicitly
    // restore its per-track gain in case a reused/native track starts muted.
    if (typeof track._setVolume === "function") track._setVolume(1);
  } catch {
    /* best-effort */
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
      options.onEvent({ type: "speech_started" });
      return;
    }
    if (type === "input_audio_buffer.speech_stopped") {
      options.onEvent({ type: "speech_stopped" });
      return;
    }
    if (type === "response.created") {
      assistantTranscript = "";
      options.onEvent({ type: "response_started" });
      return;
    }
    if (type === "conversation.item.input_audio_transcription.completed") {
      const text = transcriptFromEvent(event);
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
      options.onEvent({ type: "response_done" });
      return;
    }
    if (type === "error") {
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
    // Match OpenAI's WebRTC flow: add the microphone, create a normal offer,
    // set it locally, then exchange SDP with /v1/realtime/calls.
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await waitForIceGathering(pc);
    const sdp = String(pc.localDescription?.sdp || offer.sdp || "");
    if (!sdp) throw new Error("Could not create realtime audio offer");
    debug("sending-sdp", {
      hasAudio: sdp.includes("m=audio"),
      hasData: sdp.includes("m=application"),
    });

    const answer = await speechApi.exchangeRealtimeSdp(options.token, {
      sdp,
      chatId: options.chatId,
    });
    callId = answer.call_id ?? null;
    debug("received-sdp-answer", {
      hasAudio: answer.sdp.includes("m=audio"),
      hasData: answer.sdp.includes("m=application"),
    });
    await pc.setRemoteDescription(
      new webrtc.RTCSessionDescription({ type: "answer", sdp: answer.sdp }),
    );

    // ontrack fires before setRemoteDescription resolves in react-native-webrtc,
    // but also inspect receivers defensively so a remote audio track can never
    // stay disabled simply because a platform skipped the JS track callback.
    for (const receiver of pc.getReceivers?.() ?? []) {
      if (receiver.track?.kind === "audio") {
        remoteAudioTracks.add(receiver.track);
        enableRemoteAudioTrack(receiver.track);
      }
    }

    // Do not call RTCAudioSession.audioSessionDidActivate() here. That hook is
    // specifically for CallKit-managed activation. Recall is not using CallKit;
    // react-native-webrtc must own its normal capture/playback audio session.

    // Do not report Live Talk as recording until OpenAI's data channel is
    // actually usable. Previously this function returned after SDP alone, so a
    // failed ICE handshake looked like a working session that never answered.
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
      for (const track of localStream.getAudioTracks()) track.enabled = !muted;
      debug("microphone-muted", muted);
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
