/** Device TTS via expo-speech; optional cloud TTS via /speech/tts. */

import { cacheDirectory, writeAsStringAsync, EncodingType } from "expo-file-system/legacy";

import { requestRaw } from "@/lib/api/client";
import { canUseVoiceInput } from "@/lib/expoRuntime";
import { markdownToPlainText } from "@/lib/markdownPlain";
import {
  alignPcmBytes,
  concatBytes,
  looksLikeMpeg,
  pcmToWavBytes,
  TTS_FIRST_CLIP_BYTES,
  TTS_NEXT_CLIP_BYTES,
  TTS_PCM_SAMPLE_RATE,
  uint8ToBase64,
} from "@/lib/ttsPcm";
import { getTtsModel, TTS_DEVICE_MODEL } from "@/lib/ttsPreference";
import { loadExpoAudio } from "@/lib/voiceAudio";

type SpeechModule = typeof import("expo-speech");

/** undefined = not loaded yet; null = unavailable or failed to load. */
let speechModule: SpeechModule | null | undefined;
let cloudPlayerCleanup: (() => void) | null = null;
let ttsAbort: AbortController | null = null;
/** Bumped on every stop / new speak so in-flight work cannot start device TTS. */
let speakGeneration = 0;

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

function isCurrentSpeak(generation: number): boolean {
  return generation === speakGeneration;
}

function stopCloudPlayer(): void {
  const cleanup = cloudPlayerCleanup;
  cloudPlayerCleanup = null;
  if (cloudPlaybackFinish) {
    cloudPlaybackFinish();
    cloudPlaybackFinish = null;
  }
  try {
    cleanup?.();
  } catch {
    /* ignore */
  }
}

function stopDeviceSpeech(): void {
  const Speech = loadSpeech();
  if (!Speech) return;
  try {
    Speech.stop();
  } catch {
    speechModule = null;
  }
}

const TTS_STREAM_TIMEOUT_MS = 180_000;

async function fetchCloudTtsStream(
  token: string,
  text: string,
  language: string | undefined,
  model: string | undefined,
  signal?: AbortSignal,
): Promise<Response> {
  return requestRaw(
    "/speech/tts/stream",
    token,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/octet-stream",
      },
      body: JSON.stringify({
        text: text.slice(0, 4000).trim(),
        language: language ?? null,
        model: model ?? null,
      }),
      signal,
    },
    true,
    TTS_STREAM_TIMEOUT_MS,
  );
}

function chunkToUint8(value: Uint8Array | undefined): Uint8Array {
  if (!value) return new Uint8Array();
  return value instanceof Uint8Array ? value : new Uint8Array(value);
}

async function drainStreamBytes(
  initial: Uint8Array,
  reader: ReadableStreamDefaultReader<Uint8Array>,
): Promise<Uint8Array> {
  let buffer = initial;
  while (true) {
    const { done, value } = await reader.read();
    if (done) return buffer;
    buffer = concatBytes(buffer, chunkToUint8(value));
  }
}

/** Cloud TTS clip playback (expo-audio). Never mix with expo-speech. */
type PlaybackHandle = {
  addListener: (
    event: "playbackStatusUpdate",
    listener: (status: { didJustFinish: boolean }) => void,
  ) => { remove: () => void };
};

const CLOUD_PLAYBACK_MAX_MS = 300_000;
let cloudPlaybackFinish: (() => void) | null = null;

function waitUntilPlaybackEnds(player: PlaybackHandle, maxMs = CLOUD_PLAYBACK_MAX_MS): Promise<void> {
  return new Promise((resolve) => {
    let settled = false;
    let sub: { remove: () => void } | null = null;
    const finish = () => {
      if (settled) return;
      settled = true;
      if (cloudPlaybackFinish === finish) cloudPlaybackFinish = null;
      clearTimeout(timer);
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
    const timer = setTimeout(finish, maxMs);
  });
}

async function playCloudBase64(
  audioBase64: string,
  contentType: string,
  generation: number,
  maxWaitMs?: number,
): Promise<SpeakResult> {
  const Audio = loadExpoAudio();
  if (!Audio || !cacheDirectory) return { ok: false, reason: "unavailable" };
  if (!isCurrentSpeak(generation)) return { ok: true };
  try {
    // Only stop the previous clip — never abort this utterance's fetches.
    stopCloudPlayer();
    stopDeviceSpeech();
    const ext = contentType.includes("wav") ? "wav" : "mp3";
    const path = `${cacheDirectory}recall-tts-${Date.now()}.${ext}`;
    await writeAsStringAsync(path, audioBase64, { encoding: EncodingType.Base64 });
    if (!isCurrentSpeak(generation)) return { ok: true };
    const player = Audio.createAudioPlayer(path);
    cloudPlayerCleanup = () => {
      try {
        player.pause();
      } catch {
        /* ignore */
      }
      try {
        player.remove();
      } catch {
        /* ignore */
      }
    };
    player.play();
    await waitUntilPlaybackEnds(player, maxWaitMs ?? CLOUD_PLAYBACK_MAX_MS);
    if (!isCurrentSpeak(generation)) return { ok: true };
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
    const generation = speakGeneration;
    const player = Audio.createAudioPlayer(url);
    cloudPlayerCleanup = () => {
      try {
        player.pause();
      } catch {
        /* ignore */
      }
      try {
        player.remove();
      } catch {
        /* ignore */
      }
    };
    player.play();
    await waitUntilPlaybackEnds(player);
    if (!isCurrentSpeak(generation)) return { ok: true };
    return { ok: true };
  } catch {
    return { ok: false, reason: "error" };
  }
}

function beginDeviceSpeech(
  text: string,
  language: string,
  generation: number,
): Promise<SpeakResult> {
  if (!isCurrentSpeak(generation)) return Promise.resolve({ ok: true });
  const Speech = loadSpeech();
  if (!Speech) return Promise.resolve({ ok: false, reason: "unavailable" });
  const plain = text.slice(0, 8000).trim();
  if (!plain) return Promise.resolve({ ok: false, reason: "error" });
  return new Promise((resolve) => {
    try {
      Speech.speak(plain, {
        language,
        rate: 0.92,
        onDone: () => resolve({ ok: true }),
        onStopped: () => resolve({ ok: true }),
        onError: () => resolve({ ok: false, reason: "error" }),
      });
    } catch {
      speechModule = null;
      resolve({ ok: false, reason: "unavailable" });
    }
  });
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && (error.name === "AbortError" || error.name === "CanceledError");
}

async function playStreamingCloudTts(
  token: string,
  text: string,
  language: string,
  model: string,
  generation: number,
  signal: AbortSignal,
): Promise<SpeakResult> {
  const response = await fetchCloudTtsStream(token, text, language, model, signal);
  if (!isCurrentSpeak(generation)) return { ok: true };
  if (!response.ok) return { ok: false, reason: "error" };
  if (!response.body) return { ok: false, reason: "unavailable" };

  const reader = response.body.getReader();
  const first = await reader.read();
  if (!isCurrentSpeak(generation)) {
    await reader.cancel().catch(() => undefined);
    return { ok: true };
  }
  if (first.done || !first.value?.length) {
    return { ok: false, reason: "error" };
  }

  let buffer = chunkToUint8(first.value);
  if (looksLikeMpeg(buffer)) {
    const all = await drainStreamBytes(buffer, reader);
    if (!isCurrentSpeak(generation)) return { ok: true };
    return playCloudBase64(uint8ToBase64(all), "audio/mpeg", generation);
  }

  let awaitingFirstClip = true;
  let playTail: Promise<SpeakResult> = Promise.resolve({ ok: true });

  const enqueuePcm = (pcm: Uint8Array) => {
    const copy = pcm.slice();
    const b64 = uint8ToBase64(pcmToWavBytes(copy));
    const clipMs = Math.ceil((copy.length / (TTS_PCM_SAMPLE_RATE * 2)) * 1000) + 160;
    playTail = playTail.then((prev) => {
      if (!prev.ok) return prev;
      if (!isCurrentSpeak(generation)) return { ok: true };
      return playCloudBase64(b64, "audio/wav", generation, clipMs);
    });
  };

  const flush = (minBytes: number, force: boolean) => {
    while (buffer.length >= (force ? 2 : minBytes)) {
      const take = force ? alignPcmBytes(buffer.length) : alignPcmBytes(minBytes);
      if (take < 2) break;
      enqueuePcm(buffer.subarray(0, take));
      buffer = buffer.subarray(take);
      awaitingFirstClip = false;
      if (force) break;
    }
  };

  flush(TTS_FIRST_CLIP_BYTES, false);
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!isCurrentSpeak(generation)) {
      await reader.cancel().catch(() => undefined);
      return { ok: true };
    }
    if (value?.length) {
      buffer = concatBytes(buffer, chunkToUint8(value));
      flush(awaitingFirstClip ? TTS_FIRST_CLIP_BYTES : TTS_NEXT_CLIP_BYTES, false);
    }
  }
  flush(2, true);
  return playTail;
}

/**
 * Cloud TTS streams PCM and starts playback on the first ~120ms.
 * Device speech is a separate setting — this path never starts it.
 */
export async function speakPlainText(
  text: string,
  language = "en-US",
  options?: { token?: string | null },
): Promise<SpeakResult> {
  stopSpeaking();
  const generation = speakGeneration;
  const plain = markdownToPlainText(text).slice(0, 4000);
  if (!plain) return { ok: false, reason: "error" };

  const ttsModel = await getTtsModel();
  if (!isCurrentSpeak(generation)) return { ok: true };

  const token = options?.token ?? null;
  const useCloud =
    Boolean(token && canUseVoiceInput()) && ttsModel !== TTS_DEVICE_MODEL;
  if (!useCloud || !token) {
    return beginDeviceSpeech(plain, language, generation);
  }

  const ac = new AbortController();
  ttsAbort = ac;
  try {
    return await playStreamingCloudTts(
      token,
      plain,
      language,
      ttsModel,
      generation,
      ac.signal,
    );
  } catch (error) {
    if (isAbortError(error) || !isCurrentSpeak(generation)) {
      return { ok: true };
    }
    return { ok: false, reason: "error" };
  }
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
  speakGeneration += 1;
  ttsAbort?.abort();
  ttsAbort = null;
  stopCloudPlayer();
  stopDeviceSpeech();
}

/** Placeholder for future Whisper-based pronunciation check. */
export async function scorePronunciation(_audioUri: string, _expectedWord: string): Promise<null> {
  return null;
}

export function isSpeechAvailable(): boolean {
  return loadSpeech() !== null || loadExpoAudio() !== null;
}
