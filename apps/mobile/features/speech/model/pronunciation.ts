/** Device TTS via expo-speech; optional cloud TTS via /speech/tts. */

import { isAbortError } from "@/lib/api/abort";
import { cacheDirectory, deleteAsync, writeAsStringAsync, EncodingType } from "expo-file-system/legacy";
import { AppState, Platform } from "react-native";

import { newAccountFile } from "@/lib/accountFiles";
import {
  applySpeechRate,
  PLAYBACK_POLL_MS,
  PLAYBACK_STATUS_MS,
  playbackStatusFinished,
} from "@/features/speech/model/cloudPlayback";
import { markdownToSpeechText } from "@/lib/markdown/plain";
import { readAloudPart } from "@/features/speech/model/readAloudLength";
import {
  endReadAloud,
  readAloudChunk,
  readAloudClipEnded,
  readAloudClipTime,
  readAloudPaused,
  readAloudPlaying,
  startReadAloud,
} from "@/features/speech/model/readAloudSession";
import { ensureChunk, ensurePrefetchState } from "@/features/speech/model/ttsClipFetch";
import { currentSpeechRate, getSpeechRate } from "@/features/speech/model/speechRate";
import { getTtsModel, TTS_DEVICE_MODEL, TTS_FAST_MODEL } from "@/features/speech/model/ttsPreference";
import { loadExpoAudio, preparePlaybackAudioMode } from "@/lib/speech/voiceAudio";

export { readAloudIsCut } from "@/features/speech/model/readAloudLength";

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

/** Sync require keeps expo-speech in the main bundle (async import() breaks Metro module IDs).
 * Mic permission is not required — read-aloud is independent of voice input. */
function loadSpeech(): SpeechModule | null {
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

type SpeakResult = { ok: true } | { ok: false; reason: "unavailable" | "error" };

function isCurrentSpeak(generation: number): boolean {
  return generation === speakGeneration;
}

let backgroundStop: { remove: () => void } | null = null;

/**
 * Read-aloud ends when the app goes to the background. expo-audio pauses
 * players there (no `shouldPlayInBackground`), and the clip queue read that
 * pause as the end of a clip: it fetched and started the next clip in the
 * background. One listener for the app's lifetime, added on first use.
 */
function stopReadingInBackground(): void {
  if (backgroundStop) return;
  backgroundStop = AppState.addEventListener("change", (state) => {
    if (state === "background") stopReadingAloud();
  });
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

type PlaybackStatus = {
  didJustFinish?: boolean;
  currentTime?: number;
  duration?: number;
  playing?: boolean;
};

/** Cloud TTS clip playback (expo-audio). Never mix with expo-speech. */
type PlaybackHandle = {
  play: () => void;
  setPlaybackRate?: (rate: number, pitchCorrectionQuality?: "low" | "medium" | "high") => void;
  shouldCorrectPitch?: boolean;
  pause: () => void;
  remove: () => void;
  currentTime?: number;
  duration?: number;
  playing?: boolean;
  addListener: (
    event: "playbackStatusUpdate",
    listener: (status: PlaybackStatus) => void,
  ) => { remove: () => void };
};

const CLOUD_PLAYBACK_MAX_MS = 300_000;
/** expo-speech at 1× sounded rushed; this is "normal" before the user's speed. */
const DEVICE_SPEECH_RATE = 0.92;
let cloudPlaybackFinish: (() => void) | null = null;

function waitUntilPlaybackEnds(player: PlaybackHandle, maxMs = CLOUD_PLAYBACK_MAX_MS): Promise<void> {
  return new Promise((resolve) => {
    let settled = false;
    let sawPlaying = false;
    let sub: { remove: () => void } | null = null;
    const finish = () => {
      if (settled) return;
      settled = true;
      if (cloudPlaybackFinish === finish) cloudPlaybackFinish = null;
      clearTimeout(timer);
      clearInterval(poll);
      try {
        sub?.remove();
      } catch {
        /* ignore */
      }
      resolve();
    };
    cloudPlaybackFinish = finish;
    // A paused clip stopped playing but has not finished: the player's pause holds it.
    sub = player.addListener("playbackStatusUpdate", (status) => {
      if (status.playing) sawPlaying = true;
      readAloudClipTime(status.currentTime, status.duration);
      if (!readAloudPaused() && playbackStatusFinished({ ...status, sawPlaying })) finish();
    });
    const poll = setInterval(() => {
      if (player.playing) sawPlaying = true;
      if (
        !readAloudPaused() &&
        playbackStatusFinished({
          currentTime: player.currentTime,
          duration: player.duration,
          playing: player.playing,
          sawPlaying,
        })
      ) {
        finish();
      }
    }, PLAYBACK_POLL_MS);
    // The backstop for a clip that never reports its end; time spent paused does not count.
    const backstop = () => {
      if (readAloudPaused()) timer = setTimeout(backstop, maxMs);
      else finish();
    };
    let timer = setTimeout(backstop, maxMs);
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
  let written: string | null = null;
  try {
    // Only stop the previous clip — never abort this utterance's fetches.
    stopCloudPlayer();
    stopDeviceSpeech();
    const path = newAccountFile("speech", contentType.includes("wav") ? "wav" : "mp3");
    written = path;
    await writeAsStringAsync(path, audioBase64, { encoding: EncodingType.Base64 });
    if (!isCurrentSpeak(generation)) {
      discardClip(path);
      return { ok: true };
    }
    const player = Audio.createAudioPlayer(path, {
      updateInterval: PLAYBACK_STATUS_MS,
    }) as PlaybackHandle;
    applySpeechRate(player, currentSpeechRate());
    const release = () => {
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
      // Each clip is written fresh; nothing reads this file again.
      void deleteAsync(path, { idempotent: true }).catch(() => undefined);
    };
    cloudPlayerCleanup = release;
    player.play();
    logTtsSpeechStarted();
    readAloudPlaying({ pause: () => player.pause(), resume: () => player.play(), canPause: true }, true);
    await waitUntilPlaybackEnds(player, maxWaitMs ?? CLOUD_PLAYBACK_MAX_MS);
    // Release on finish, not on the next tap: a finished player keeps the
    // audio session in playback and holds the decoder.
    if (cloudPlayerCleanup === release) {
      cloudPlayerCleanup = null;
      release();
      readAloudClipEnded();
    }
    return { ok: true };
  } catch {
    if (written) discardClip(written);
    return { ok: false, reason: "error" };
  }
}

function discardClip(path: string): void {
  void deleteAsync(path, { idempotent: true }).catch(() => undefined);
}

async function beginDeviceSpeech(
  text: string,
  language: string,
  generation: number,
): Promise<SpeakResult> {
  if (!isCurrentSpeak(generation)) return { ok: true };
  await preparePlaybackAudioMode();
  if (!isCurrentSpeak(generation)) return { ok: true };
  const Speech = loadSpeech();
  if (!Speech) return { ok: false, reason: "unavailable" };
  const plain = text.slice(0, 8000).trim();
  if (!plain) return { ok: false, reason: "error" };
  return new Promise((resolve) => {
    try {
      Speech.speak(plain, {
        language,
        rate: DEVICE_SPEECH_RATE * currentSpeechRate(),
        onStart: () => {
          logTtsSpeechStarted();
          // expo-speech pauses on iOS only; on Android the player offers Stop alone.
          readAloudPlaying(
            {
              pause: () => Speech.pause(),
              resume: () => Speech.resume(),
              canPause: Platform.OS === "ios",
            },
            false,
          );
        },
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
    readAloudChunk(index, state.chunks.length);
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
  options?: { token?: string | null; preferCloud?: boolean; preferFast?: boolean },
): Promise<SpeakResult> {
  markTtsTap();
  logTtsLatency("tap");
  stopSpeaking();
  stopReadingInBackground();
  const generation = speakGeneration;
  const plain = readAloudPart(markdownToSpeechText(text));
  if (!plain) return { ok: false, reason: "error" };

  const [ttsModel] = await Promise.all([getTtsModel(), getSpeechRate()]);
  if (!isCurrentSpeak(generation)) return { ok: true };

  const token = options?.token ?? null;
  await preparePlaybackAudioMode();
  if (!isCurrentSpeak(generation)) return { ok: true };
  // "Use on-device voice" wins for every plan; `preferCloud` only falls back to the phone.
  const cloudModel = ttsModel === TTS_DEVICE_MODEL ? ttsModel : options?.preferFast ? TTS_FAST_MODEL : ttsModel;
  const useCloud = Boolean(token) && cloudModel !== TTS_DEVICE_MODEL;
  if (!useCloud || !token) {
    return beginDeviceSpeech(plain, language, generation);
  }

  const ac = new AbortController();
  ttsAbort = ac;
  try {
    const played = await playChunkPipeline(
      token,
      plain,
      language,
      cloudModel,
      generation,
      ac.signal,
    );
    if (played.ok || !isCurrentSpeak(generation) || !options?.preferCloud) return played;
    return beginDeviceSpeech(plain, language, generation);
  } catch (error) {
    if (isAbortError(error) || !isCurrentSpeak(generation)) {
      return { ok: true };
    }
    if (options?.preferCloud) {
      return beginDeviceSpeech(plain, language, generation);
    }
    return { ok: false, reason: "error" };
  } finally {
    if (ttsAbort === ac) ttsAbort = null;
  }
}

/**
 * Read a reply aloud, with the small player over the composer (readAloudSession). The reading
 * belongs to the session, not to the reply's row: it goes on while the reply scrolls away, and
 * the player or the reply's speaker icon stops it.
 */
export async function readReplyAloud(
  messageId: string,
  markdown: string,
  language: string,
  options?: { token?: string | null; preferCloud?: boolean },
): Promise<SpeakResult> {
  const id = startReadAloud(messageId, markdown, stopSpeaking);
  try {
    return await speakPlainText(markdown, language, options);
  } finally {
    endReadAloud(id);
  }
}

/** Stop the reading and close its player: its Stop, the app going to the background, sign-out. */
export function stopReadingAloud(): void {
  stopSpeaking();
  endReadAloud();
}

export function stopSpeaking(): void {
  speakGeneration += 1;
  ttsAbort?.abort();
  ttsAbort = null;
  stopCloudPlayer();
  stopDeviceSpeech();
}
