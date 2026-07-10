/** Device TTS via expo-speech; optional cloud TTS via /speech/tts. */

import { cacheDirectory, writeAsStringAsync, EncodingType } from "expo-file-system/legacy";

import { apiUrl, fetchWithTimeout } from "@/lib/api/client";
import { canUseVoiceInput } from "@/lib/expoRuntime";
import { markdownToPlainText } from "@/lib/markdownPlain";
import { loadExpoAudio } from "@/lib/voiceAudio";

type SpeechModule = typeof import("expo-speech");

/** undefined = not loaded yet; null = unavailable or failed to load. */
let speechModule: SpeechModule | null | undefined;
let cloudPlayerCleanup: (() => void) | null = null;

/** Sync require keeps expo-speech in the main bundle (async import() breaks Metro module IDs). */
function loadSpeech(): SpeechModule | null {
  if (!canUseVoiceInput()) {
    speechModule = null;
    return null;
  }
  if (speechModule === null) return null;
  if (speechModule) return speechModule;
  try {
    speechModule = require("expo-speech") as SpeechModule;
    return speechModule;
  } catch {
    speechModule = null;
    return null;
  }
}

export type SpeakResult = { ok: true } | { ok: false; reason: "unavailable" | "error" };

async function fetchCloudTts(
  token: string,
  text: string,
  language?: string,
): Promise<{ audio_base64: string; content_type: string } | null> {
  const plain = markdownToPlainText(text).slice(0, 4000);
  if (!plain) return null;
  const response = await fetchWithTimeout(apiUrl("/speech/tts"), {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text: plain, language: language ?? null }),
  });
  if (!response.ok) return null;
  const data = (await response.json()) as {
    audio_base64?: string;
    content_type?: string;
  };
  if (!data.audio_base64) return null;
  return {
    audio_base64: data.audio_base64,
    content_type: data.content_type ?? "audio/mpeg",
  };
}

/** Prefer cloud TTS when token is set; fall back to on-device expo-speech. */
type PlaybackHandle = {
  addListener: (
    event: "playbackStatusUpdate",
    listener: (status: { didJustFinish: boolean }) => void,
  ) => { remove: () => void };
};

const CLOUD_PLAYBACK_MAX_MS = 300_000;
let cloudPlaybackFinish: (() => void) | null = null;

function waitUntilPlaybackEnds(player: PlaybackHandle): Promise<void> {
  return new Promise((resolve) => {
    let settled = false;
    let sub: { remove: () => void } | null = null;
    const finish = () => {
      if (settled) return;
      settled = true;
      if (cloudPlaybackFinish === finish) cloudPlaybackFinish = null;
      try {
        sub?.remove();
      } catch {
        /* ignore */
      }
      resolve();
    };
    cloudPlaybackFinish = finish;
    sub = player.addListener("playbackStatusUpdate", (status) => {
      if (status.didJustFinish) finish();
    });
    setTimeout(finish, CLOUD_PLAYBACK_MAX_MS);
  });
}

async function playCloudBase64(
  audioBase64: string,
  contentType: string,
): Promise<SpeakResult> {
  const Audio = loadExpoAudio();
  if (!Audio || !cacheDirectory) return { ok: false, reason: "unavailable" };
  try {
    stopSpeaking();
    const ext = contentType.includes("wav") ? "wav" : "mp3";
    const path = `${cacheDirectory}recall-tts-${Date.now()}.${ext}`;
    await writeAsStringAsync(path, audioBase64, { encoding: EncodingType.Base64 });
    const player = Audio.createAudioPlayer(path);
    cloudPlayerCleanup = () => {
      try {
        player.remove();
      } catch {
        /* ignore */
      }
    };
    player.play();
    await waitUntilPlaybackEnds(player);
    return { ok: true };
  } catch {
    return { ok: false, reason: "error" };
  }
}

async function playRemoteAudio(url: string): Promise<SpeakResult> {
  const Audio = loadExpoAudio();
  if (!Audio) return { ok: false, reason: "unavailable" };
  try {
    stopSpeaking();
    const player = Audio.createAudioPlayer(url);
    cloudPlayerCleanup = () => {
      try {
        player.remove();
      } catch {
        /* ignore */
      }
    };
    player.play();
    await waitUntilPlaybackEnds(player);
    return { ok: true };
  } catch {
    return { ok: false, reason: "error" };
  }
}

async function speakDevicePlainText(
  text: string,
  language: string,
): Promise<SpeakResult> {
  const plain = markdownToPlainText(text);
  if (!plain) return { ok: false, reason: "error" };

  const Speech = loadSpeech();
  if (!Speech) return { ok: false, reason: "unavailable" };

  try {
    Speech.stop();
    await new Promise<void>((resolve) => {
      Speech.speak(plain.slice(0, 8000), {
        language,
        rate: 0.92,
        onDone: () => resolve(),
        onStopped: () => resolve(),
        onError: () => resolve(),
      });
    });
    return { ok: true };
  } catch {
    speechModule = null;
    return { ok: false, reason: "unavailable" };
  }
}

/** Prefer cloud TTS when token is set; fall back to on-device expo-speech. */
export async function speakPlainText(
  text: string,
  language = "en-US",
  options?: { token?: string | null },
): Promise<SpeakResult> {
  const token = options?.token ?? null;
  if (token && canUseVoiceInput()) {
    try {
      const cloud = await fetchCloudTts(token, text, language);
      if (cloud) {
        const played = await playCloudBase64(cloud.audio_base64, cloud.content_type);
        if (played.ok) return played;
      }
    } catch {
      /* fall through */
    }
  }
  return speakDevicePlainText(text, language);
}

/** Device/cloud TTS for a single word (optional stored pronunciation clip). */
export async function speakWord(
  word: string,
  options?: { language?: string; pronunciationUrl?: string | null; token?: string | null },
): Promise<SpeakResult> {
  const language = options?.language ?? "en-US";
  const pronunciationUrl = options?.pronunciationUrl?.trim();
  if (pronunciationUrl) {
    const played = await playRemoteAudio(pronunciationUrl);
    if (played.ok) return played;
  }
  return speakPlainText(word, language, { token: options?.token });
}

export function stopSpeaking(): void {
  if (cloudPlaybackFinish) {
    cloudPlaybackFinish();
    cloudPlaybackFinish = null;
  }
  if (cloudPlayerCleanup) {
    cloudPlayerCleanup();
    cloudPlayerCleanup = null;
  }
  const Speech = loadSpeech();
  if (!Speech) return;
  try {
    Speech.stop();
  } catch {
    speechModule = null;
  }
}

/** Placeholder for future Whisper-based pronunciation check. */
export async function scorePronunciation(_audioUri: string, _expectedWord: string): Promise<null> {
  return null;
}

export function isSpeechAvailable(): boolean {
  return loadSpeech() !== null || loadExpoAudio() !== null;
}
