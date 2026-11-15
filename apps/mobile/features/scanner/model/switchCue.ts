import { EncodingType, cacheDirectory, writeAsStringAsync } from "expo-file-system/legacy";
import { useEffect } from "react";

import { encodePcm16Wav } from "@/lib/audio/wav";
import { loadExpoAudio } from "@/lib/speech/voiceAudio";

type SwitchDirection = -1 | 1;
type CuePlayer = {
  play: () => void;
  remove: () => void;
  seekTo: (seconds: number) => Promise<void>;
  currentTime: number;
  volume: number;
};

const SAMPLE_RATE = 22_050;
const DURATION_MS = 96;
const VOLUME = 0.2;
const DIRECTIONS: readonly SwitchDirection[] = [1, -1];

/**
 * Both cues are made and loaded when the scanner opens and kept until it closes. Made on the
 * first switch, the first cue was written, loaded and released 180 ms later, before a cold
 * player had started: the first switch was silent and only later ones played (2026-11-13).
 */
const players: Partial<Record<SwitchDirection, CuePlayer>> = {};
let preparing: Promise<void> | null = null;
let cueEpoch = 0;
const cueUris: Partial<Record<SwitchDirection, string>> = {};
const cueWrites: Partial<Record<SwitchDirection, Promise<string | null>>> = {};

/** A quiet 96 ms frequency sweep: tactile enough to register, never alarm-like. */
function buildScannerSwitchCueBase64(direction: SwitchDirection): string {
  const sampleCount = Math.round((DURATION_MS / 1000) * SAMPLE_RATE);
  const samples = new Int16Array(sampleCount);
  let phase = 0;
  for (let i = 0; i < sampleCount; i += 1) {
    const progress = i / Math.max(1, sampleCount - 1);
    const swept = direction > 0 ? progress : 1 - progress;
    const frequency = 760 + swept * 820;
    phase += (2 * Math.PI * frequency) / SAMPLE_RATE;
    const edge = Math.min(progress / 0.08, (1 - progress) / 0.24, 1);
    const sample = Math.sin(phase) * Math.max(0, edge) * 0.24;
    samples[i] = Math.round(sample * 32767);
  }
  return encodePcm16Wav(samples, SAMPLE_RATE);
}

async function cueFileUri(direction: SwitchDirection): Promise<string | null> {
  const cached = cueUris[direction];
  if (cached) return cached;
  const inFlight = cueWrites[direction];
  if (inFlight) return inFlight;
  const write = (async () => {
    if (!cacheDirectory) return null;
    const directionName = direction > 0 ? "forward" : "back";
    const path = `${cacheDirectory}recall-scanner-switch-${directionName}.wav`;
    await writeAsStringAsync(path, buildScannerSwitchCueBase64(direction), {
      encoding: EncodingType.Base64,
    });
    cueUris[direction] = path;
    return path;
  })();
  cueWrites[direction] = write;
  try {
    return await write;
  } finally {
    delete cueWrites[direction];
  }
}

/** Makes and loads both cues while the scanner opens, so the first switch sounds at once. */
export function prepareScannerSwitchCue(): Promise<void> {
  if (preparing) return preparing;
  const epoch = cueEpoch;
  let run: Promise<void> | null = null;
  run = (async () => {
    try {
      const Audio = loadExpoAudio();
      if (!Audio) return;
      for (const direction of DIRECTIONS) {
        if (players[direction]) continue;
        const uri = await cueFileUri(direction);
        // Closed while the file was written: nothing to keep.
        if (!uri || epoch !== cueEpoch) return;
        const player = Audio.createAudioPlayer(uri) as CuePlayer;
        player.volume = VOLUME;
        players[direction] = player;
      }
    } catch {
      /* Optional feedback must never block scanner controls. */
    } finally {
      if (preparing === run) preparing = null;
    }
  })();
  preparing = run;
  return run;
}

/** Frees both cues: the scanner closed. A preparation still running keeps nothing. */
export function stopScannerSwitchCue(): void {
  cueEpoch += 1;
  // A preparation still running belongs to the closed scanner; the next opening makes its own.
  preparing = null;
  for (const direction of DIRECTIONS) {
    const player = players[direction];
    delete players[direction];
    try {
      player?.remove();
    } catch {
      /* Optional feedback must never block scanner controls. */
    }
  }
}

export async function playScannerSwitchCue(direction: SwitchDirection): Promise<void> {
  try {
    if (!players[direction]) await prepareScannerSwitchCue();
    const player = players[direction];
    if (!player) return;
    // A cue that played before sits at its end: back to the start, then play.
    if (player.currentTime > 0) await player.seekTo(0);
    player.play();
  } catch {
    // A player that failed is freed; the next switch makes the cues again.
    stopScannerSwitchCue();
  }
}

/** The cues live while the scanner is open: made as it opens, freed as it closes or goes. */
export function useScannerSwitchCue(visible: boolean): void {
  useEffect(() => {
    if (!visible) return undefined;
    void prepareScannerSwitchCue();
    return stopScannerSwitchCue;
  }, [visible]);
}
