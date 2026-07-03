/** Guarded loader for expo-audio — skipped in Expo Go (native module not present). */

import type { PermissionResponse } from "expo-audio";
import { getInfoAsync, readAsStringAsync } from "expo-file-system/legacy";

import { canUseVoiceInput } from "@/lib/expoRuntime";

type ExpoAudioModule = typeof import("expo-audio");

/** undefined = not loaded yet; null = unavailable or failed to load. */
let audioModule: ExpoAudioModule | null | undefined;

const MIN_RECORDING_BYTES = 800;

const MIME_BY_EXT: Record<string, string> = {
  m4a: "audio/m4a",
  mp4: "audio/mp4",
  caf: "audio/x-caf",
  "3gp": "audio/3gpp",
  webm: "audio/webm",
  wav: "audio/wav",
};

/** Sync require keeps expo-audio in the main bundle (async import() breaks Metro module IDs). */
export function loadExpoAudio(): ExpoAudioModule | null {
  if (!canUseVoiceInput()) {
    audioModule = null;
    return null;
  }
  if (audioModule === null) return null;
  if (audioModule) return audioModule;
  try {
    audioModule = require("expo-audio") as ExpoAudioModule;
    return audioModule;
  } catch {
    audioModule = null;
    return null;
  }
}

export function isVoiceInputAvailable(): boolean {
  return loadExpoAudio() !== null;
}

export type MeterListener = (level: number) => void;

export type VoiceRecorder = {
  stop: () => Promise<string | null>;
  subscribeMetering: (listener: MeterListener) => () => void;
};

/** Map expo-audio dB metering (-160…0) to a 0–1 visual level. */
export function normalizeMetering(db?: number): number {
  if (db == null || db <= -160) return 0.12;
  const clamped = Math.max(-60, Math.min(0, db));
  return 0.1 + ((clamped + 60) / 60) * 0.9;
}

export function normalizeRecordingUri(uri: string): string {
  if (uri.startsWith("file://")) return uri;
  return `file://${uri}`;
}

export function speechUploadFromUri(uri: string): { uri: string; name: string; type: string } {
  const normalized = normalizeRecordingUri(uri);
  const fileName = normalized.split("/").pop() ?? "speech.m4a";
  const ext = fileName.includes(".") ? (fileName.split(".").pop()?.toLowerCase() ?? "m4a") : "m4a";
  const name = fileName.includes(".") ? fileName : `speech.${ext}`;
  return {
    uri: normalized,
    name,
    type: MIME_BY_EXT[ext] ?? "audio/m4a",
  };
}

async function waitForRecordingFile(uri: string, attempts = 5): Promise<number | null> {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const info = await getInfoAsync(uri);
      const size = info.exists ? (info.size ?? 0) : 0;
      if (size >= MIN_RECORDING_BYTES) return size;
    } catch {
      /* retry */
    }
    await new Promise((resolve) => setTimeout(resolve, 120));
  }
  return null;
}

export async function readRecordingBase64(uri: string): Promise<string | null> {
  const upload = speechUploadFromUri(uri);
  const size = await waitForRecordingFile(upload.uri);
  if (!size) return null;
  try {
    return await readAsStringAsync(upload.uri, { encoding: "base64" });
  } catch {
    return null;
  }
}

export async function requestVoicePermission(
  mod: ExpoAudioModule,
): Promise<PermissionResponse> {
  return mod.requestRecordingPermissionsAsync();
}

export async function startVoiceRecording(): Promise<VoiceRecorder | null> {
  const mod = loadExpoAudio();
  if (!mod) return null;

  await mod.setAudioModeAsync({
    allowsRecording: true,
    playsInSilentMode: true,
  });

  const recorder = new mod.AudioModule.AudioRecorder({});
  const preset = {
    ...mod.RecordingPresets.HIGH_QUALITY,
    isMeteringEnabled: true,
  };
  await recorder.prepareToRecordAsync(preset);
  recorder.record();

  const listeners = new Set<MeterListener>();
  const tick = setInterval(() => {
    if (!recorder.isRecording) return;
    try {
      const level = normalizeMetering(recorder.getStatus().metering);
      listeners.forEach((listener) => listener(level));
    } catch {
      /* best-effort metering */
    }
  }, 60);

  return {
    stop: async () => {
      clearInterval(tick);
      if (recorder.isRecording) {
        await recorder.stop();
      }
      const rawUri = recorder.uri;
      if (!rawUri) return null;
      const uri = normalizeRecordingUri(rawUri);
      const size = await waitForRecordingFile(uri);
      if (!size) return null;
      return uri;
    },
    subscribeMetering: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

export const VOICE_INPUT_REBUILD_HINT =
  "Voice input needs a dev build with expo-audio. Rebuild:\n\ncd apps/mobile && pnpm expo run:android   # or run:ios";
