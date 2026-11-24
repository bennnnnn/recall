import type { SharedValue } from "react-native-reanimated";
import React, { useLayoutEffect } from "react";
import { NativeModules, Text } from "react-native";
import { act, render, screen, waitFor } from "@testing-library/react-native";
import * as webrtc from "react-native-webrtc";

import { useComposerDictation } from "@/features/chat/hooks/useComposerDictation";
import { speechApi } from "@/features/speech/api";
import { VoiceComposerWaveform } from "@/features/speech/components/VoiceComposerWaveform";
import { transcribeSpeech, type User } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/errorBody";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { reportFailure } from "@/lib/sentry";
import { startVoiceRecording } from "@/lib/speech/voiceAudio";

// The composer mic on a build with WebRTC: the words land in the draft while the user
// speaks. The call is a fake whose data channel delivers OpenAI's transcription events.

jest.mock("react-native-reanimated", () => {
  const { View } = jest.requireActual("react-native");
  const linear = (t: number) => t;
  return {
    __esModule: true,
    default: { View },
    Easing: { linear, ease: linear, sin: linear, inOut: () => linear, out: () => linear, in: () => linear, cubic: linear },
    // Stable across renders, as Reanimated's own.
    useSharedValue: (init: number) => {
      const { useState } = jest.requireActual("react");
      const [shared] = useState(() => {
        const value = { value: init, set: (next: number) => { value.value = next; } };
        return value;
      });
      return shared;
    },
    useAnimatedStyle: (fn: () => object) => fn(),
    useAnimatedReaction: () => undefined,
    withTiming: (v: number) => v,
    withRepeat: (v: number) => v,
  };
});
jest.mock("expo-modules-core", () => ({ requireOptionalNativeModule: () => null }));
jest.mock("@/lib/api", () => ({ transcribeSpeech: jest.fn() }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/contexts/AuthContext", () => ({ useAuthOptional: () => ({ profileValidated: true }) }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableError: jest.fn() }));
jest.mock("@/lib/sentry", () => ({ reportFailure: jest.fn() }));
jest.mock("@/ui/overlay/dialogs", () => ({ offerSettings: jest.fn(async () => false) }));
jest.mock("@/lib/speech/voiceAudio", () => ({
  VOICE_MAX_RECORDING_MS: 45_000,
  isVoiceInputAvailable: () => true,
  loadExpoAudio: () => ({}),
  requestVoicePermission: jest.fn(async () => ({ granted: true })),
  startVoiceRecording: jest.fn(async () => ({ stop: async () => null, subscribeMetering: () => () => {} })),
  deleteVoiceRecording: jest.fn(async () => undefined),
  yieldMicToWebRtc: jest.fn(async () => undefined),
  meteringLevel: () => 0.12,
}));
jest.mock("@/features/speech/api", () => ({
  speechApi: {
    createDictationSession: jest.fn(),
    connectDictationSession: jest.fn(),
    endDictationSession: jest.fn(async () => undefined),
  },
  speechLanguageHint: () => "am",
}));
jest.mock("react-native-webrtc", () => ({
  mediaDevices: { getUserMedia: jest.fn() },
  RTCPeerConnection: jest.fn(),
  RTCSessionDescription: jest.fn((value) => value),
}));

type Channel = {
  readyState: string;
  send: jest.Mock;
  close: jest.Mock;
  onopen?: () => void;
  onmessage?: (message: { data: unknown }) => void;
};

const plusUser = { plan: "plus", features: ["speech_transcription"] } as unknown as User;
const track = { kind: "audio", enabled: true, stop: jest.fn() };
const peerClose = jest.fn();
let channel: Channel;
let input = "";
const setInput = jest.fn((next: string | ((prev: string) => string)) => {
  input = typeof next === "function" ? next(input) : next;
});
const openUpgrade = jest.fn();
let current: ReturnType<typeof useComposerDictation>;

function Probe() {
  const dictation = useComposerDictation({
    token: "tok",
    user: plusUser,
    routeChatId: "chat-1",
    setInput,
    openUpgrade,
    t: (key) => key,
  });
  useLayoutEffect(() => { current = dictation; });
  const active = dictation.voiceRecording || dictation.voiceTranscribing;
  return active ? (
    <VoiceComposerWaveform
      recording={dictation.voiceRecording}
      transcribing={dictation.voiceTranscribing}
      meterLevel={dictation.voiceMeterLevel as SharedValue<number>}
    />
  ) : (
    <Text>field</Text>
  );
}

const emit = async (event: object) => {
  await act(async () => { channel.onmessage?.({ data: JSON.stringify(event) }); });
};
const delta = (item: string, text: string) =>
  emit({ type: "conversation.item.input_audio_transcription.delta", item_id: item, delta: text });
const completed = (item: string, transcript: string) =>
  emit({ type: "conversation.item.input_audio_transcription.completed", item_id: item, transcript });
const sent = () => channel.send.mock.calls.map(([value]) => JSON.parse(value as string));
const refusal = (status: number, code: string) =>
  new ApiRequestError(status, JSON.stringify({ detail: { code, message: code } }));

async function startTake(caret: { start: number; end: number } | null = null) {
  await render(<Probe />);
  await act(async () => { current.toggleVoiceInput(caret); });
}

beforeEach(() => {
  jest.clearAllMocks();
  (NativeModules as Record<string, unknown>).WebRTCModule = {};
  (globalThis as unknown as { __DEV__: boolean }).__DEV__ = false;
  input = "";
  track.enabled = true;
  channel = { readyState: "open", send: jest.fn(), close: jest.fn() };
  (webrtc.mediaDevices.getUserMedia as jest.Mock).mockResolvedValue({
    getAudioTracks: () => [track],
    getTracks: () => [track],
  });
  (webrtc.RTCPeerConnection as unknown as jest.Mock).mockImplementation(() => ({
    addTrack: jest.fn(),
    createDataChannel: () => channel,
    createOffer: async () => ({ sdp: "v=0\nm=audio" }),
    setLocalDescription: async () => undefined,
    setRemoteDescription: async () => { channel.onopen?.(); },
    getReceivers: () => [],
    close: peerClose,
  }));
  (speechApi.createDictationSession as jest.Mock).mockResolvedValue({
    call_id: "dict-1",
    expires_at: 1,
    model: "gpt-live-transcribe",
    max_duration_seconds: 45,
  });
  (speechApi.connectDictationSession as jest.Mock).mockResolvedValue({ sdp: "v=0\nm=audio answer" });
});

afterEach(() => {
  delete (NativeModules as Record<string, unknown>).WebRTCModule;
});

it("puts the words in the draft at the caret as they are spoken, and the stop lands the last ones", async () => {
  input = "Dear Sam,Thanks.";
  await startTake({ start: 9, end: 9 });
  await waitFor(() => expect(speechApi.connectDictationSession).toHaveBeenCalled());
  // The offer went through Recall's dictation route; no OpenAI secret is on the phone.
  expect((speechApi.connectDictationSession as jest.Mock).mock.calls[0][1]).toEqual({
    callId: "dict-1",
    sdp: "v=0\nm=audio",
  });
  expect(speechApi.createDictationSession).toHaveBeenCalledWith("tok", { language: "am" });
  expect(current.voiceRecording).toBe(true);

  await delta("i1", " see");
  expect(input).toBe("Dear Sam, see Thanks.");
  expect(screen.getByTestId("voice-live-words")).toHaveTextContent("see");
  await delta("i1", " you");
  expect(input).toBe("Dear Sam, see you Thanks.");
  // The stretch's final text replaces its words.
  await completed("i1", "See you");
  expect(input).toBe("Dear Sam, See you Thanks.");
  await delta("i2", " at noon");
  expect(input).toBe("Dear Sam, See you at noon Thanks.");
  expect(screen.getByTestId("voice-live-words")).toHaveTextContent("See you at noon");

  // Stop: the rest of the audio is committed, and its final text lands. No upload.
  await act(async () => { current.toggleVoiceInput(); });
  await waitFor(() => expect(sent()).toContainEqual({ type: "input_audio_buffer.commit" }));
  expect(current.voiceTranscribing).toBe(true);
  // The words stay up while the last ones land; no "Transcribing…" wait.
  expect(screen.getByTestId("voice-live-words")).toHaveTextContent("See you at noon");
  expect(screen.queryByText("chat.voice_transcribing")).toBeNull();
  expect(track.enabled).toBe(false);

  await emit({ type: "input_audio_buffer.committed", item_id: "i2", previous_item_id: "i1" });
  await completed("i2", "at noon.");
  await waitFor(() => expect(current.voiceTranscribing).toBe(false));
  expect(input).toBe("Dear Sam, See you at noon. Thanks.");
  expect(speechApi.endDictationSession).toHaveBeenCalledWith("tok", "dict-1", true);
  expect(peerClose).toHaveBeenCalled();
  expect(transcribeSpeech).not.toHaveBeenCalled();
  expect(startVoiceRecording).not.toHaveBeenCalled();
  expect(screen.getByText("field")).toBeOnTheScreen();
});

it("follows the draft with the words when the field was not being edited", async () => {
  input = "Typed first";
  await startTake(null);
  await waitFor(() => expect(speechApi.connectDictationSession).toHaveBeenCalled());
  await delta("i1", " then spoken");
  expect(input).toBe("Typed first then spoken");
});

it("says it is starting while the call connects", async () => {
  (speechApi.createDictationSession as jest.Mock).mockReturnValue(new Promise(() => undefined));
  await startTake();
  expect(screen.getByText("chat.voice_starting")).toBeOnTheScreen();
  // A stop before the call connects drops the take: nothing was heard yet.
  await act(async () => { current.toggleVoiceInput(); });
  expect(current.voiceRecording).toBe(false);
  expect(screen.getByText("field")).toBeOnTheScreen();
});

it("leaves the draft as it was and says so when nothing was heard", async () => {
  input = "draft";
  await startTake();
  await waitFor(() => expect(speechApi.connectDictationSession).toHaveBeenCalled());
  await act(async () => { current.toggleVoiceInput(); });
  await waitFor(() => expect(sent()).toContainEqual({ type: "input_audio_buffer.commit" }));
  await emit({ type: "error", error: { code: "input_audio_buffer_commit_empty" } });
  await waitFor(() => expect(current.voiceTranscribing).toBe(false));
  expect(input).toBe("draft");
  expect(reportRecoverableError).toHaveBeenCalledWith(null, "chat.voice_transcribe_empty");
  // The server gives the day's voice input back.
  expect(speechApi.endDictationSession).toHaveBeenCalledWith("tok", "dict-1", false);
});

it("keeps what was heard when the call drops mid-take", async () => {
  await startTake();
  await waitFor(() => expect(speechApi.connectDictationSession).toHaveBeenCalled());
  await delta("i1", " half a thought");
  const pc = (webrtc.RTCPeerConnection as unknown as jest.Mock).mock.results[0].value as {
    connectionState?: string;
    onconnectionstatechange?: () => void;
  };
  await act(async () => {
    pc.connectionState = "failed";
    pc.onconnectionstatechange?.();
  });
  expect(input).toBe("half a thought");
  expect(current.voiceRecording).toBe(false);
  expect(reportFailure).toHaveBeenCalledWith("live_dictation", expect.any(Error));
  expect(speechApi.endDictationSession).toHaveBeenCalledWith("tok", "dict-1", true);
});

describe("the recorded fallback", () => {
  it("records the clip in Expo Go, which has no WebRTC", async () => {
    delete (NativeModules as Record<string, unknown>).WebRTCModule;
    await startTake();
    await waitFor(() => expect(startVoiceRecording).toHaveBeenCalled());
    expect(speechApi.createDictationSession).not.toHaveBeenCalled();
  });

  it("records the clip, saying nothing, on a server without live dictation", async () => {
    (speechApi.createDictationSession as jest.Mock).mockRejectedValue(refusal(503, "not_configured"));
    await startTake();
    await waitFor(() => expect(startVoiceRecording).toHaveBeenCalled());
    expect(current.voiceRecording).toBe(true);
    expect(reportFailure).not.toHaveBeenCalled();
    expect(reportRecoverableError).not.toHaveBeenCalled();
  });

  it("records the clip and reports it when the call could not be made", async () => {
    (speechApi.connectDictationSession as jest.Mock).mockRejectedValue(refusal(502, "upstream_failed"));
    await startTake();
    await waitFor(() => expect(startVoiceRecording).toHaveBeenCalled());
    expect(reportFailure).toHaveBeenCalledWith("live_dictation", expect.any(ApiRequestError));
    // The minted session is ended, and its voice input given back.
    await waitFor(() =>
      expect(speechApi.endDictationSession).toHaveBeenCalledWith("tok", "dict-1", false),
    );
    expect(peerClose).toHaveBeenCalled();
  });

  it("opens the plans, recording nothing, when the plan has no voice input", async () => {
    (speechApi.createDictationSession as jest.Mock).mockRejectedValue(refusal(403, "not_in_plan"));
    await startTake();
    await waitFor(() => expect(openUpgrade).toHaveBeenCalledWith("voice"));
    expect(startVoiceRecording).not.toHaveBeenCalled();
    expect(current.voiceRecording).toBe(false);
  });

  it("says the day's voice input is used, recording nothing", async () => {
    (speechApi.createDictationSession as jest.Mock).mockRejectedValue(refusal(429, "daily_limit"));
    await startTake();
    await waitFor(() =>
      expect(reportRecoverableError).toHaveBeenCalledWith(null, "chat.voice_daily_limit"),
    );
    expect(startVoiceRecording).not.toHaveBeenCalled();
  });
});
