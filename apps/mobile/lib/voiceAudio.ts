/** Lazy loader for expo-audio — skipped in Expo Go (native module not present). */

import type { PermissionResponse } from "expo-audio";

import { canUseVoiceInput } from "@/lib/expoRuntime";

type ExpoAudioModule = typeof import("expo-audio");

let audioModule: ExpoAudioModule | null | undefined;

export async function loadExpoAudio(): Promise<ExpoAudioModule | null> {
  if (!canUseVoiceInput()) {
    audioModule = null;
    return null;
  }
  if (audioModule === null) return null;
  if (audioModule) return audioModule;
  try {
    audioModule = await import("expo-audio");
    return audioModule;
  } catch {
    audioModule = null;
    return null;
  }
}

export async function isVoiceInputAvailable(): Promise<boolean> {
  return (await loadExpoAudio()) !== null;
}

export type VoiceRecorder = {
  stop: () => Promise<string | null>;
};

export async function requestVoicePermission(
  mod: ExpoAudioModule,
): Promise<PermissionResponse> {
  return mod.requestRecordingPermissionsAsync();
}

export async function startVoiceRecording(): Promise<VoiceRecorder | null> {
  const mod = await loadExpoAudio();
  if (!mod) return null;

  await mod.setAudioModeAsync({
    allowsRecording: true,
    playsInSilentMode: true,
  });

  const recorder = new mod.AudioModule.AudioRecorder(mod.RecordingPresets.HIGH_QUALITY);
  await recorder.prepareToRecordAsync();
  recorder.record();

  return {
    stop: async () => {
      await recorder.stop();
      return recorder.uri;
    },
  };
}

export const VOICE_INPUT_REBUILD_HINT =
  "Voice input needs a dev build with expo-audio. Rebuild:\n\ncd apps/mobile && pnpm expo run:android   # or run:ios";
