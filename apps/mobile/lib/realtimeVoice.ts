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
  RTCAudioSession?: {
    audioSessionDidActivate: () => void;
    audioSessionDidDeactivate: () => void;
  };
};

export type RealtimeVoiceSession = {
  callId: string | null;
  setMuted: (muted: boolean) => void;
  cancelResponse: () => void;
  close: () => void;
};

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

function sendRealtimeEvent(channel: { readyState?: string; send?: (data: string) => void }, type: string) {
  if (channel.readyState !== "open" || typeof channel.send !== "function") return;
  try {
    channel.send(JSON.stringify({ type }));
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
  const localStream = await webrtc.mediaDevices.getUserMedia({
    audio: webRtcMicConstraints(),
    video: false,
  });
  if (localStream.getAudioTracks().length === 0) {
    for (const track of localStream.getTracks()) track.stop();
    throw new Error("webrtc_unavailable");
  }
  // Do not call RTCAudioSession.audioSessionDidActivate — that API is for
  // CallKit. Invoking it here tells WebRTC the session is already running
  // and the capture unit never starts (packetsSent stays 0).
  const pc = new webrtc.RTCPeerConnection({});
  for (const track of localStream.getTracks()) {
    pc.addTrack(track, localStream);
  }
  pc.ontrack = (ev: { track?: { enabled?: boolean } }) => {
    if (ev.track) ev.track.enabled = true;
  };

  const dataChannel = pc.createDataChannel("oai-events");
  let assistantTranscript = "";
  let closed = false;
  let callId: string | null = null;
  // iOS getUserMedia runs without VoiceProcessing (AEC deadlocks Simulator).
  // Speaker output therefore loops into the mic and server_vad barges in.
  // v1 Live Talk is half-duplex: mute send while the assistant is talking.
  let userMuted = false;
  let playbackHold = false;
  let playbackHoldTimer: ReturnType<typeof setTimeout> | null = null;
  const ECHO_HOLDOFF_MS = 500;
  const applySendMute = () => {
    const send = !(userMuted || playbackHold);
    for (const track of localStream.getAudioTracks()) track.enabled = send;
  };
  const holdMicForPlayback = () => {
    if (playbackHoldTimer != null) {
      clearTimeout(playbackHoldTimer);
      playbackHoldTimer = null;
    }
    playbackHold = true;
    applySendMute();
  };
  const releaseMicAfterPlayback = () => {
    if (playbackHoldTimer != null) clearTimeout(playbackHoldTimer);
    playbackHoldTimer = setTimeout(() => {
      playbackHoldTimer = null;
      playbackHold = false;
      applySendMute();
    }, ECHO_HOLDOFF_MS);
  };

  const emitError = (message: string) => {
    if (!closed) options.onEvent({ type: "error", message });
  };

  dataChannel.onopen = () => {
    options.onEvent({ type: "connected" });
    // Semantic VAD on the initial /realtime/calls session never produced
    // speech_started here; server_vad is energy-based and is what OpenAI
    // documents as the WebRTC default.
    try {
      dataChannel.send(
        JSON.stringify({
          type: "session.update",
          session: {
            type: "realtime",
            audio: {
              input: {
                turn_detection: {
                  type: "server_vad",
                  create_response: true,
                  interrupt_response: false,
                  threshold: 0.65,
                  prefix_padding_ms: 300,
                  silence_duration_ms: 500,
                },
              },
            },
          },
        }),
      );
    } catch {
      /* session.update is best-effort; create_response still runs */
    }
  };
  dataChannel.onerror = () => emitError("Realtime voice data channel failed");
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
      holdMicForPlayback();
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
      releaseMicAfterPlayback();
      options.onEvent({ type: "response_done" });
      return;
    }
    if (type === "error") {
      const raw = event.error;
      const messageText =
        raw && typeof raw === "object" && "message" in raw
          ? String((raw as { message?: unknown }).message || "Realtime voice failed")
          : "Realtime voice failed";
      emitError(messageText);
    }
  };

  const tearDownAudio = () => {
    if (playbackHoldTimer != null) {
      clearTimeout(playbackHoldTimer);
      playbackHoldTimer = null;
    }
    for (const track of localStream.getTracks()) track.stop();
    pc.close();
  };

  try {
    const offer = await pc.createOffer({ offerToReceiveAudio: true });
    await pc.setLocalDescription(offer);
    // Do not wait for ICE gathering. Embedding candidates in the offer
    // crashes the iOS Simulator inside setRemoteDescription (AURemoteIO).
    const sdp = String(offer.sdp || pc.localDescription?.sdp || "");
    if (!sdp) throw new Error("Could not create realtime audio offer");
    const answer = await speechApi.exchangeRealtimeSdp(options.token, {
      sdp,
      chatId: options.chatId,
    });
    callId = answer.call_id ?? null;
    await pc.setRemoteDescription(
      new webrtc.RTCSessionDescription({ type: "answer", sdp: answer.sdp }),
    );
  } catch (error) {
    tearDownAudio();
    throw error;
  }

  return {
    callId,
    setMuted: (muted: boolean) => {
      userMuted = muted;
      applySendMute();
    },
    cancelResponse: () => sendRealtimeEvent(dataChannel, "response.cancel"),
    close: () => {
      if (closed) return;
      closed = true;
      try {
        dataChannel.close();
      } catch {
        /* best-effort */
      }
      tearDownAudio();
    },
  };
}
