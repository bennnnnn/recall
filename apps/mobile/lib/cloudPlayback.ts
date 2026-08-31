/** Duration-accurate cloud clip wait so live-talk splices do not click or stall. */

export const PLAYBACK_WAIT_SLACK_MS = 400;
export const PLAYBACK_WAIT_MIN_MS = 250;
/** Failed duration must not stall the clip queue (~20s × N ≈ a minute of silence). */
export const PLAYBACK_WAIT_UNKNOWN_MS = 2_000;
/** Live-talk clips are 0.5–1.5s; never wait a whole utterance on one splice. */
export const PLAYBACK_WAIT_CLIP_MAX_MS = 2_500;
const LIVE_TALK_BYTE_RATE = 24000 * 2;

export function wavDurationMsFromBase64(b64: string): number | null {
  const fromHeader = wavDurationMsFromHeader(b64);
  if (fromHeader != null) return fromHeader;
  return wavDurationMsFromPayloadSize(b64);
}

export function playbackWaitMs(durationMs: number | null): number {
  if (durationMs == null || durationMs <= 0) return PLAYBACK_WAIT_UNKNOWN_MS;
  return Math.min(
    PLAYBACK_WAIT_CLIP_MAX_MS,
    Math.max(PLAYBACK_WAIT_MIN_MS, durationMs + PLAYBACK_WAIT_SLACK_MS),
  );
}

export function playbackStatusFinished(status: {
  didJustFinish?: boolean;
  currentTime?: number;
  duration?: number;
  playing?: boolean;
  sawPlaying?: boolean;
}): boolean {
  if (status.didJustFinish) return true;
  if (status.sawPlaying && status.playing === false) return true;
  const duration = status.duration ?? 0;
  const current = status.currentTime ?? 0;
  return duration > 0 && current >= duration - 0.04;
}

function wavDurationMsFromHeader(b64: string): number | null {
  const header = decodeBase64Prefix(b64, 128);
  if (!header || header.length < 44) return null;
  if (
    header[0] !== 0x52 ||
    header[1] !== 0x49 ||
    header[2] !== 0x46 ||
    header[3] !== 0x46
  ) {
    return null;
  }
  let offset = 12;
  let byteRate = 0;
  let dataSize = 0;
  while (offset + 8 <= header.length) {
    const id = String.fromCharCode(
      header[offset] ?? 0,
      header[offset + 1] ?? 0,
      header[offset + 2] ?? 0,
      header[offset + 3] ?? 0,
    );
    const size =
      (header[offset + 4] ?? 0) |
      ((header[offset + 5] ?? 0) << 8) |
      ((header[offset + 6] ?? 0) << 16) |
      ((header[offset + 7] ?? 0) << 24);
    if (id === "fmt " && offset + 16 <= header.length) {
      byteRate =
        (header[offset + 16] ?? 0) |
        ((header[offset + 17] ?? 0) << 8) |
        ((header[offset + 18] ?? 0) << 16) |
        ((header[offset + 19] ?? 0) << 24);
    }
    if (id === "data") {
      dataSize = size;
      break;
    }
    if (size <= 0) break;
    offset += 8 + size + (size % 2);
  }
  if (byteRate <= 0 || dataSize <= 0) return null;
  return Math.ceil((dataSize / byteRate) * 1000);
}

function wavDurationMsFromPayloadSize(b64: string): number | null {
  let pad = 0;
  if (b64.endsWith("==")) pad = 2;
  else if (b64.endsWith("=")) pad = 1;
  const bytes = Math.floor((b64.length * 3) / 4) - pad;
  if (bytes <= 44) return null;
  return Math.max(1, Math.ceil(((bytes - 44) / LIVE_TALK_BYTE_RATE) * 1000));
}

function decodeBase64Prefix(b64: string, byteCount: number): Uint8Array | null {
  const chars = Math.ceil(byteCount / 3) * 4;
  try {
    const binary = atob(b64.slice(0, chars));
    const out = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      out[i] = binary.charCodeAt(i);
    }
    return out;
  } catch {
    return null;
  }
}
