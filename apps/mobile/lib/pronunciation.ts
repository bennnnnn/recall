/** Device TTS via expo-speech; optional cloud TTS via /speech/tts. */

import { cacheDirectory, writeAsStringAsync, EncodingType } from "expo-file-system/legacy";

import { requestRaw } from "@/lib/api/client";
import { canUseVoiceInput } from "@/lib/expoRuntime";
import { markdownToPlainText } from "@/lib/markdownPlain";
import { splitTtsChunks } from "@/lib/ttsLead";
import { getTtsModel, TTS_DEVICE_MODEL } from "@/lib/ttsPreference";
import { loadExpoAudio } from "@/lib/voiceAudio";

type SpeechModule = typeof import("expo-speech");

/** undefined = not loaded yet; null = unavailable or failed to load. */
let speechModule: SpeechModule | null | undefined;
let cloudPlayerCleanup: (() => void) | null = null;
let ttsAbort: AbortController | null = null;
/** Bumped on every stop / new speak so in-flight work cannot start device TTS. */
let speakGeneration = 0;
let ttsTapAt = 0;
let ttsStartLoggedFor = -1;

function markTtsTap(): void {
  ttsTapAt = Date.now();
  ttsStartLoggedFor = -1;
}

function ttsElapsedMs(): number {
  return ttsTapAt > 0 ? Date.now() - ttsTapAt : 0;
}

function logTtsLatency(stage: string, extra?: Record<string, string | number | boolean>): void {
  console.info("[tts-latency]", { ms: ttsElapsedMs(), stage, ...extra });
}

function logTtsSpeechStarted(): void {
  if (ttsStartLoggedFor === speakGeneration) return;
  ttsStartLoggedFor = speakGeneration;
  logTtsLatency("speech_started");
}

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

const TTS_JSON_TIMEOUT_MS = 60_000;

type TtsClip = { audio_base64: string; content_type: string };

type PrefetchState = {
  key: string;
  model: string;
  chunks: string[];
  abort: AbortController;
  clips: Array<TtsClip | null>;
  inflight: Array<Promise<TtsClip | null> | null>;
};

let prefetch: PrefetchState | null = null;

function prefetchCacheKey(text: string, model: string): string {
  return `${model}\0${text}`;
}

async function fetchCloudTtsClip(
  token: string,
  text: string,
  language: string,
  model: string,
  part: "full" | "lead" | "rest",
  signal: AbortSignal,
): Promise<TtsClip | null> {
  const plain = text.slice(0, 4000).trim();
  if (!plain) return null;
  const response = await requestRaw(
    "/speech/tts",
    token,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: plain,
        language,
        model,
        part,
      }),
      signal,
    },
    true,
    TTS_JSON_TIMEOUT_MS,
  );
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
    logTtsSpeechStarted();
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
        onStart: () => logTtsSpeechStarted(),
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

function ttsPartForChunk(index: number, total: number): "full" | "lead" | "rest" {
  if (total <= 1) return "full";
  return index === 0 ? "lead" : "rest";
}

function ensurePrefetchState(text: string, model: string): PrefetchState {
  const key = prefetchCacheKey(text, model);
  if (prefetch?.key === key) return prefetch;
  prefetch?.abort.abort();
  const chunks = splitTtsChunks(text);
  const next: PrefetchState = {
    key,
    model,
    chunks,
    abort: new AbortController(),
    clips: chunks.map(() => null),
    inflight: chunks.map(() => null),
  };
  prefetch = next;
  return next;
}

function ensureChunk(
  state: PrefetchState,
  index: number,
  token: string,
  language: string,
  signal: AbortSignal,
): Promise<TtsClip | null> {
  const cached = state.clips[index];
  if (cached) return Promise.resolve(cached);
  const pending = state.inflight[index];
  if (pending) return pending;
  const chunk = state.chunks[index];
  if (!chunk) return Promise.resolve(null);
  const request = fetchCloudTtsClip(
    token,
    chunk,
    language,
    state.model,
    ttsPartForChunk(index, state.chunks.length),
    signal,
  )
    .then((clip) => {
      if (state.clips[index] == null) state.clips[index] = clip;
      if (state.inflight[index] === request) state.inflight[index] = null;
      return state.clips[index];
    })
    .catch((error: unknown) => {
      if (state.inflight[index] === request) state.inflight[index] = null;
      if (isAbortError(error)) return state.clips[index];
      throw error;
    });
  state.inflight[index] = request;
  return request;
}

/** Warm the first clip of the latest assistant reply so tap is not a 10s OpenRouter wait. */
export async function prefetchReadAloud(
  text: string,
  token: string | null,
): Promise<void> {
  if (!token || !canUseVoiceInput() || ttsAbort) return;
  const model = await getTtsModel();
  if (model === TTS_DEVICE_MODEL) return;
  const plain = markdownToPlainText(text).slice(0, 4000);
  if (!plain) return;
  const state = ensurePrefetchState(plain, model);
  if (state.clips[0] || state.inflight[0]) {
    if (state.chunks.length > 1 && !state.clips[1] && !state.inflight[1]) {
      void ensureChunk(state, 1, token, "en-US", state.abort.signal);
    }
    return;
  }
  logTtsLatency("prefetch_start", {
    leadChars: state.chunks[0]?.length ?? 0,
    chunks: state.chunks.length,
  });
  try {
    const clip = await ensureChunk(state, 0, token, "en-US", state.abort.signal);
    if (prefetch !== state) return;
    logTtsLatency("prefetch_ready", { ok: Boolean(clip), chunks: state.chunks.length });
    if (clip && state.chunks.length > 1) {
      void ensureChunk(state, 1, token, "en-US", state.abort.signal);
    }
  } catch (error) {
    if (isAbortError(error)) return;
    logTtsLatency("prefetch_failed");
  }
}

async function playChunkPipeline(
  token: string,
  text: string,
  language: string,
  model: string,
  generation: number,
  signal: AbortSignal,
): Promise<SpeakResult> {
  const state = ensurePrefetchState(text, model);
  const first = state.chunks[0];
  if (!first) return { ok: false, reason: "error" };
  const cached = Boolean(state.clips[0]);
  logTtsLatency("lead_request", {
    leadChars: first.length,
    chunks: state.chunks.length,
    cached,
  });
  const leadClip = await ensureChunk(state, 0, token, language, signal);
  if (!isCurrentSpeak(generation)) return { ok: true };
  if (!leadClip) {
    logTtsLatency("lead_failed");
    return { ok: false, reason: "error" };
  }
  logTtsLatency("lead_ready", { leadChars: first.length, cached });

  for (let index = 0; index < state.chunks.length; index += 1) {
    if (!isCurrentSpeak(generation)) return { ok: true };
    const clip =
      index === 0 ? leadClip : await ensureChunk(state, index, token, language, signal);
    if (!clip) return index === 0 ? { ok: false, reason: "error" } : { ok: true };
    if (index + 1 < state.chunks.length) {
      void ensureChunk(state, index + 1, token, language, signal);
    }
    const played = await playCloudBase64(clip.audio_base64, clip.content_type, generation);
    if (!played.ok) return played;
  }
  return { ok: true };
}

/**
 * Cloud TTS plays a finished WAV/MP3 for the first sentence, then the rest.
 * Raw PCM streaming caused static and waited for the full body on device.
 */
export async function speakPlainText(
  text: string,
  language = "en-US",
  options?: { token?: string | null },
): Promise<SpeakResult> {
  markTtsTap();
  logTtsLatency("tap");
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
    return await playChunkPipeline(
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
  } finally {
    if (ttsAbort === ac) ttsAbort = null;
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
