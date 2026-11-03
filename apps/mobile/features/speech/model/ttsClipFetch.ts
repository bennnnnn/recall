/**
 * The cloud voice's clips for read-aloud: one request per chunk of a reply (the first
 * sentence as a short "lead", then the rest), fetched ahead of playback and kept for the
 * reply being read, so a second tap on the same reply plays without asking again.
 */

import { isAbortError } from "@/lib/api/abort";
import { requestRaw } from "@/lib/api/client";
import { readAloudPart } from "@/features/speech/model/readAloudLength";
import { splitTtsChunks } from "@/features/speech/model/ttsLead";

const TTS_JSON_TIMEOUT_MS = 60_000;

export type TtsClip = { audio_base64: string; content_type: string; lead_hash?: string | null };

export type PrefetchState = {
  key: string;
  model: string;
  chunks: string[];
  abort: AbortController;
  clips: (TtsClip | null)[];
  inflight: (Promise<TtsClip | null> | null)[];
  leadHash: string | null;
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

export function ensurePrefetchState(text: string, model: string): PrefetchState {
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
    leadHash: null,
  };
  prefetch = next;
  return next;
}

export function ensureChunk(
  state: PrefetchState,
  index: number,
  token: string,
  language: string,
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
    language,
    state.model,
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
      if (isAbortError(error)) return state.clips[index];
      throw error;
    });
  state.inflight[index] = request;
  return request;
}
