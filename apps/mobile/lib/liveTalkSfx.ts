import { EncodingType, cacheDirectory, writeAsStringAsync } from "expo-file-system/legacy";

import { notifySuccess, tap } from "@/lib/haptics";
import { loadExpoAudio } from "@/lib/voiceAudio";

export type LiveTalkCue = "start" | "end";

/** One open chime when the overlay appears; one close chime when it leaves. */
export function liveTalkCueForVisibility(
  visible: boolean,
  wasVisible: boolean,
): LiveTalkCue | null {
  if (visible && !wasVisible) return "start";
  if (!visible && wasVisible) return "end";
  return null;
}

/** Rising open / falling close — short enough to overlap connect/teardown. */
export const LIVE_TALK_CUE_TONES: Record<LiveTalkCue, readonly { hz: number; ms: number }[]> = {
  start: [
    { hz: 659, ms: 90 },
    { hz: 880, ms: 170 },
  ],
  end: [
    { hz: 784, ms: 90 },
    { hz: 523, ms: 190 },
  ],
};

const SAMPLE_RATE = 22_050;
const AMPLITUDE = 0.22;
const GAP_MS = 24;

type CuePlayer = {
  play: () => void;
  remove: () => void;
};

let cuePlayer: CuePlayer | null = null;
const cueUriByKind: Partial<Record<LiveTalkCue, string>> = {};
const cueWrite: Partial<Record<LiveTalkCue, Promise<string | null>>> = {};

function uint8ToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i] ?? 0);
  }
  return btoa(binary);
}

function writeInt16LE(view: DataView, offset: number, value: number): void {
  view.setInt16(offset, value, true);
}

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i));
  }
}

/** 16-bit mono WAV. Envelope avoids clicks. */
export function buildLiveTalkCueWavBase64(kind: LiveTalkCue): string {
  const tones = LIVE_TALK_CUE_TONES[kind];
  const totalMs = tones.reduce((sum, tone) => sum + tone.ms, 0) + GAP_MS * (tones.length - 1);
  const sampleCount = Math.max(1, Math.round((totalMs / 1000) * SAMPLE_RATE));
  const dataBytes = sampleCount * 2;
  const buffer = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, SAMPLE_RATE, true);
  view.setUint32(28, SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, dataBytes, true);

  let sampleIndex = 0;
  const attack = Math.round(SAMPLE_RATE * 0.008);
  const release = Math.round(SAMPLE_RATE * 0.04);
  for (let t = 0; t < tones.length; t += 1) {
    const tone = tones[t];
    if (!tone) continue;
    const n = Math.round((tone.ms / 1000) * SAMPLE_RATE);
    for (let i = 0; i < n && sampleIndex < sampleCount; i += 1) {
      const env =
        i < attack ? i / attack : i > n - release ? Math.max(0, (n - i) / release) : 1;
      const sample = Math.sin((2 * Math.PI * tone.hz * i) / SAMPLE_RATE) * AMPLITUDE * env;
      writeInt16LE(view, 44 + sampleIndex * 2, Math.max(-32767, Math.min(32767, sample * 32767)));
      sampleIndex += 1;
    }
    if (t < tones.length - 1) {
      const gap = Math.round((GAP_MS / 1000) * SAMPLE_RATE);
      sampleIndex = Math.min(sampleCount, sampleIndex + gap);
    }
  }

  return uint8ToBase64(new Uint8Array(buffer));
}

async function cueFileUri(kind: LiveTalkCue): Promise<string | null> {
  const cached = cueUriByKind[kind];
  if (cached) return cached;
  const inflight = cueWrite[kind];
  if (inflight) return inflight;
  const write = (async () => {
    if (!cacheDirectory) return null;
    const path = `${cacheDirectory}recall-live-talk-${kind}.wav`;
    await writeAsStringAsync(path, buildLiveTalkCueWavBase64(kind), {
      encoding: EncodingType.Base64,
    });
    cueUriByKind[kind] = path;
    return path;
  })();
  cueWrite[kind] = write;
  try {
    return await write;
  } finally {
    delete cueWrite[kind];
  }
}

function releaseCuePlayer(): void {
  const current = cuePlayer;
  cuePlayer = null;
  if (!current) return;
  try {
    current.remove();
  } catch {
    /* best-effort */
  }
}

/**
 * ChatGPT-style open/close chime + haptic.
 * Must not call setAudioModeAsync — that silences WebRTC capture on Simulator.
 */
export function playLiveTalkCue(kind: LiveTalkCue): void {
  if (kind === "start") notifySuccess();
  else tap();

  const Audio = loadExpoAudio();
  if (!Audio) return;
  void cueFileUri(kind)
    .then((uri) => {
      if (!uri) return;
      releaseCuePlayer();
      const player = Audio.createAudioPlayer(uri) as CuePlayer;
      cuePlayer = player;
      player.play();
    })
    .catch(() => {
      /* UI cue is best-effort; Live Talk must still connect. */
    });
}
