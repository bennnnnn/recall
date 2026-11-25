import type { SharedValue } from "react-native-reanimated";
import React, { useLayoutEffect } from "react";
import { NativeModules, Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useComposerDictation } from "@/features/chat/hooks/useComposerDictation";
import { speechApi } from "@/features/speech/api";
import type { User } from "@/lib/api";

// Opening a chat must not load WebRTC: only live talk did, and only once it started. The
// composer mic loads its call on the first tap.

let mockWebRtcLoads = 0;
jest.mock("react-native-webrtc", () => {
  mockWebRtcLoads += 1;
  return {
    mediaDevices: { getUserMedia: jest.fn(async () => { throw new Error("no mic in this test"); }) },
    RTCPeerConnection: jest.fn(),
    RTCSessionDescription: jest.fn(),
  };
});
jest.mock("react-native-reanimated", () => {
  const { View } = jest.requireActual("react-native");
  return {
    __esModule: true,
    default: { View },
    useSharedValue: (init: number) => {
      const { useState } = jest.requireActual("react");
      const [shared] = useState(() => {
        const value = { value: init, set: (next: number) => { value.value = next; } };
        return value;
      });
      return shared;
    },
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
  speechLanguageHint: () => "en",
}));

const proUser = { plan: "pro", features: ["speech_transcription"] } as unknown as User;
let current: ReturnType<typeof useComposerDictation>;

function Composer() {
  const dictation = useComposerDictation({
    token: "tok",
    user: proUser,
    routeChatId: "chat-1",
    setInput: jest.fn(),
    openUpgrade: jest.fn(),
    t: (key) => key,
  });
  useLayoutEffect(() => { current = dictation; });
  return <Text>{(dictation.voiceMeterLevel as SharedValue<number>).value}</Text>;
}

beforeEach(() => {
  (NativeModules as Record<string, unknown>).WebRTCModule = {};
});

afterEach(() => {
  delete (NativeModules as Record<string, unknown>).WebRTCModule;
});

it("renders the composer without loading WebRTC, and loads it on the first mic tap", async () => {
  await render(<Composer />);
  expect(mockWebRtcLoads).toBe(0);

  await act(async () => { current.toggleVoiceInput(null); });
  await waitFor(() => expect(mockWebRtcLoads).toBe(1));
  expect(speechApi.createDictationSession).not.toHaveBeenCalled(); // the mic failed first
});
