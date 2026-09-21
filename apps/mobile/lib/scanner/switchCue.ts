import { EncodingType, cacheDirectory, writeAsStringAsync } from "expo-file-system/legacy";

import { loadExpoAudio } from "@/lib/speech/voiceAudio";

type SwitchDirection = -1 | 1;
type CuePlayer = {
  play: () => void;
  release: () => void;
  volume: number;
};

const SAMPLE_RATE = 22_050;
const DURATION_MS = 96;
const RELEASE_DELAY_MS = 180;
const VOLUME = 0.2;

let activePlayer: CuePlayer | null = null;
let releaseTimer: ReturnType<typeof setTimeout> | null = null;
let cueEpoch = 0;
const cueUris: Partial<Record<SwitchDirection, string>> = {};
const cueWrites: Partial<Record<SwitchDirection, Promise<string | null>>> = {};

function uint8ToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i] ?? 0);
  }
  return btoa(binary);
}

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i));
  }
}

/** A quiet 96 ms frequency sweep: tactile enough to register, never alarm-like. */
export function buildScannerSwitchCueBase64(direction: SwitchDirection): string {
  const sampleCount = Math.round((DURATION_MS / 1000) * SAMPLE_RATE);
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

  let phase = 0;
  for (let i = 0; i < sampleCount; i += 1) {
    const progress = i / Math.max(1, sampleCount - 1);
    const swept = direction > 0 ? progress : 1 - progress;
    const frequency = 760 + swept * 820;
    phase += (2 * Math.PI * frequency) / SAMPLE_RATE;
    const edge = Math.min(progress / 0.08, (1 - progress) / 0.24, 1);
    const sample = Math.sin(phase) * Math.max(0, edge) * 0.24;
    view.setInt16(44 + i * 2, Math.round(sample * 32767), true);
  }
  return uint8ToBase64(new Uint8Array(buffer));
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

export function stopScannerSwitchCue(): void {
  cueEpoch += 1;
  if (releaseTimer) clearTimeout(releaseTimer);
  releaseTimer = null;
  const player = activePlayer;
  activePlayer = null;
  try {
    player?.release();
  } catch {
    /* Optional feedback must never block scanner controls. */
  }
}

export async function playScannerSwitchCue(direction: SwitchDirection): Promise<void> {
  const epoch = ++cueEpoch;
  try {
    const Audio = loadExpoAudio();
    if (!Audio) return;
    const uri = await cueFileUri(direction);
    if (!uri || epoch !== cueEpoch) return;
    if (releaseTimer) clearTimeout(releaseTimer);
    releaseTimer = null;
    try {
      activePlayer?.release();
    } catch {
      /* Replaced by the next switch cue. */
    }
    const player = Audio.createAudioPlayer(uri) as CuePlayer;
    activePlayer = player;
    player.volume = VOLUME;
    player.play();
    releaseTimer = setTimeout(stopScannerSwitchCue, RELEASE_DELAY_MS);
  } catch {
    stopScannerSwitchCue();
  }
}
