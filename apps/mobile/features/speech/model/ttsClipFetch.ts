/**
 * The cloud voice's clips for read-aloud: one request per chunk of a reply (the first
 * sentence as a short "lead", then the rest), fetched ahead of playback and kept for the
 * reply being read, so a second tap on the same reply plays without asking again.
 */

import { requestRaw } from "@/lib/api/client";
import { readAloudPart } from "@/features/speech/model/readAloudLength";
import { splitTtsChunks } from "@/features/speech/model/ttsLead";

const TTS_JSON_TIMEOUT_MS = 60_000;

type TtsClip = { audio_base64: string; content_type: string; lead_hash?: string | null };

/**
 * Everything the server's audio depends on besides the text: the model, the user's voice
 * (the server reads it off the account) and the language. The speed is not here: the phone
 * applies it to the player. Keyed on the model alone, a reply replayed after the voice changed
 * played the old voice.
 */
export type ClipVoice = { model: string; voice: string | null; language: string };

type PrefetchState = {
  key: string;
  voice: ClipVoice;
  chunks: string[];
  abort: AbortController;
  clips: (TtsClip | null)[];
  inflight: (Promise<TtsClip | null> | null)[];
  leadHash: string | null;
};

let prefetch: PrefetchState | null = null;

function prefetchCacheKey(text: string, { model, voice, language }: ClipVoice): string {
  return [model, voice ?? "", language, text].join("\0");
}

async function fetchCloudTtsClip(
  token: string,
  text: string,
  language: string,
  model: string,
  part: "full" | "lead" | "rest",
  signal: AbortSignal,
  leadHash?: string | null,
): Promise<TtsClip | null> {
  const plain = readAloudPart(text);
  if (!plain) return null;
  const body: Record<string, string> = {
    text: plain,
    language,
    model,
    part,
  };
  if (part === "rest" && leadHash) {
    body.lead_hash = leadHash;
  }
  const response = await requestRaw(
    "/speech/tts",
    token,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    },
    true,
    TTS_JSON_TIMEOUT_MS,
  );
  if (!response.ok) return null;
  const data = (await response.json()) as {
    audio_base64?: string;
    content_type?: string;
    lead_hash?: string | null;
  };
  if (!data.audio_base64) return null;
  return {
    audio_base64: data.audio_base64,
    content_type: data.content_type ?? "audio/mpeg",
    lead_hash: data.lead_hash ?? null,
  };
}

function ttsPartForChunk(index: number, total: number): "full" | "lead" | "rest" {
  if (total <= 1) return "full";
  return index === 0 ? "lead" : "rest";
}

export function ensurePrefetchState(text: string, voice: ClipVoice): PrefetchState {
  const key = prefetchCacheKey(text, voice);
  if (prefetch?.key === key) return prefetch;
  prefetch?.abort.abort();
  const chunks = splitTtsChunks(text);
  const next: PrefetchState = {
    key,
    voice,
    chunks,
    abort: new AbortController(),
    clips: chunks.map(() => null),
    inflight: chunks.map(() => null),
    leadHash: null,
  };
  prefetch = next;
  return next;
}

export function ensureChunk(
  state: PrefetchState,
  index: number,
  token: string,
  signal: AbortSignal,
): Promise<TtsClip | null> {
  const cached = state.clips[index];
  if (cached) {
    if (cached.lead_hash) state.leadHash = cached.lead_hash;
    return Promise.resolve(cached);
  }
  const pending = state.inflight[index];
  if (pending) return pending;
  const chunk = state.chunks[index];
  if (!chunk) return Promise.resolve(null);
  const request = fetchCloudTtsClip(
    token,
    chunk,
    state.voice.language,
    state.voice.model,
    ttsPartForChunk(index, state.chunks.length),
    signal,
    state.leadHash,
  )
    .then((clip) => {
      if (clip?.lead_hash) state.leadHash = clip.lead_hash;
      if (state.clips[index] == null) state.clips[index] = clip;
      if (state.inflight[index] === request) state.inflight[index] = null;
      return state.clips[index];
    })
    .catch((error: unknown) => {
      if (state.inflight[index] === request) state.inflight[index] = null;
      // Only the reading's own Stop is a cancel. A deadline is an AbortError too, and a failure:
      // the reading falls back to the phone's voice rather than end mid-reply.
      if (signal.aborted) return state.clips[index];
      throw error;
    });
  state.inflight[index] = request;
  return request;
}

/**
 * Ask for a chunk before the reading reaches it. Nothing awaits this request yet, so its
 * rejection is handled here: a cancel (Stop, or the next reply read) settles it unseen, and a
 * failure (a deadline included) is the reading's to meet when it asks for the chunk again on
 * reaching it. Left to `void`, a Stop during the first clip logged the second clip's cancelled
 * download as "Uncaught (in promise)".
 */
export function prefetchChunk(
  state: PrefetchState,
  index: number,
  token: string,
  signal: AbortSignal,
): Promise<void> {
  return ensureChunk(state, index, token, signal).then(
    () => undefined,
    (error: unknown) => {
      if (signal.aborted) return;
      console.info("[tts-latency]", { stage: "prefetch_failed", chunk: index, error: errorName(error) });
    },
  );
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : typeof error;
}
