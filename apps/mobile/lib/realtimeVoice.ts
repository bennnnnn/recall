import { Platform } from "react-native";

import { speechApi } from "@/lib/api/speech";
import {
  LIVE_TALK_ECHO_GUARD_MS,
  liveTalkHoldMicForAssistant,
  liveTalkUplinkMuted,
} from "@/lib/liveTalkLogic";
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
  try {
    webrtc.RTCAudioSession?.audioSessionDidActivate();
  } catch {
    /* optional iOS helper */
  }
  const pc = new webrtc.RTCPeerConnection({});
  for (const track of localStream.getTracks()) {
    pc.addTrack(track, localStream);
  }

  const dataChannel = pc.createDataChannel("oai-events");
  let assistantTranscript = "";
  let closed = false;
  let callId: string | null = null;
  let userMuted = false;
  let playbackHold = false;
  let unmuteTimer: ReturnType<typeof setTimeout> | null = null;

  const applyUplinkMute = () => {
    const muted = liveTalkUplinkMuted(userMuted, playbackHold);
    for (const track of localStream.getAudioTracks()) track.enabled = !muted;
  };

  const emitError = (message: string) => {
    if (!closed) options.onEvent({ type: "error", message });
  };

  dataChannel.onopen = () => {
    options.onEvent({ type: "connected" });
  };
  dataChannel.onerror = () => emitError("Realtime voice data channel failed");
  dataChannel.onmessage = (message: { data?: unknown }) => {
    if (typeof message.data !== "string") return;
    let event: Record<string, unknown>;
    try {
      event = JSON.parse(message.data) as Record<string, unknown>;
    } catch {
      return;
    }
    const type = typeof event.type === "string" ? event.type : "";
    if (type === "input_audio_buffer.speech_started") {
      const hold = liveTalkHoldMicForAssistant("speech_started", playbackHold);
      if (hold.dropSpeechStarted) return;
      options.onEvent({ type: "speech_started" });
      return;
    }
    if (type === "input_audio_buffer.speech_stopped") {
      options.onEvent({ type: "speech_stopped" });
      return;
    }
    if (type === "response.created") {
      assistantTranscript = "";
      const hold = liveTalkHoldMicForAssistant("response_started", playbackHold);
      playbackHold = hold.holding;
      if (unmuteTimer != null) {
        clearTimeout(unmuteTimer);
        unmuteTimer = null;
      }
      applyUplinkMute();
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
      const hold = liveTalkHoldMicForAssistant("response_done", playbackHold);
      if (unmuteTimer != null) clearTimeout(unmuteTimer);
      unmuteTimer = setTimeout(() => {
        unmuteTimer = null;
        playbackHold = hold.holding;
        applyUplinkMute();
      }, LIVE_TALK_ECHO_GUARD_MS);
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
    try {
      webrtc.RTCAudioSession?.audioSessionDidDeactivate();
    } catch {
      /* best-effort */
    }
    for (const track of localStream.getTracks()) track.stop();
    pc.close();
  };

  try {
    const offer = await pc.createOffer({ offerToReceiveAudio: true });
    await pc.setLocalDescription(offer);
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
      applyUplinkMute();
    },
    cancelResponse: () => sendRealtimeEvent(dataChannel, "response.cancel"),
    close: () => {
      if (closed) return;
      closed = true;
      if (unmuteTimer != null) {
        clearTimeout(unmuteTimer);
        unmuteTimer = null;
      }
      try {
        dataChannel.close();
      } catch {
        /* best-effort */
      }
      tearDownAudio();
    },
  };
}
