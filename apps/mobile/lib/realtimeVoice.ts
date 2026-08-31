import { speechApi } from "@/lib/api/speech";

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

function loadWebRtc(): NativeWebRtc {
  // Native module: this intentionally requires a dev-client / production build,
  // not Expo Go. Keeping require() here avoids loading native code for users who
  // never open Live Talk.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require("react-native-webrtc") as NativeWebRtc;
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
  const localStream = await webrtc.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
    video: false,
  });
  const pc = new webrtc.RTCPeerConnection({});
  for (const track of localStream.getTracks()) {
    pc.addTrack(track, localStream);
  }

  const dataChannel = pc.createDataChannel("oai-events");
  let assistantTranscript = "";
  let closed = false;
  let callId: string | null = null;

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
      const raw = event.error;
      const messageText =
        raw && typeof raw === "object" && "message" in raw
          ? String((raw as { message?: unknown }).message || "Realtime voice failed")
          : "Realtime voice failed";
      emitError(messageText);
    }
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
    for (const track of localStream.getTracks()) track.stop();
    pc.close();
    throw error;
  }

  return {
    callId,
    setMuted: (muted: boolean) => {
      for (const track of localStream.getAudioTracks()) track.enabled = !muted;
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
      for (const track of localStream.getTracks()) track.stop();
      pc.close();
    },
  };
}
