/** Duration-accurate cloud clip wait so live-talk splices do not click or stall. */

export const PLAYBACK_WAIT_SLACK_MS = 400;
export const PLAYBACK_WAIT_MIN_MS = 250;
export const PLAYBACK_WAIT_UNKNOWN_MS = 20_000;

export function wavDurationMsFromBase64(b64: string): number | null {
  const header = decodeBase64Prefix(b64, 44);
  if (!header || header.length < 44) return null;
  if (
    header[0] !== 0x52 ||
    header[1] !== 0x49 ||
    header[2] !== 0x46 ||
    header[3] !== 0x46
  ) {
    return null;
  }
  const byteRate =
    (header[28] ?? 0) |
    ((header[29] ?? 0) << 8) |
    ((header[30] ?? 0) << 16) |
    ((header[31] ?? 0) << 24);
  const dataSize =
    (header[40] ?? 0) |
    ((header[41] ?? 0) << 8) |
    ((header[42] ?? 0) << 16) |
    ((header[43] ?? 0) << 24);
  if (byteRate <= 0 || dataSize <= 0) return null;
  return Math.ceil((dataSize / byteRate) * 1000);
}

export function playbackWaitMs(durationMs: number | null): number {
  if (durationMs == null || durationMs <= 0) return PLAYBACK_WAIT_UNKNOWN_MS;
  return Math.max(PLAYBACK_WAIT_MIN_MS, durationMs + PLAYBACK_WAIT_SLACK_MS);
}

export function playbackStatusFinished(status: {
  didJustFinish?: boolean;
  currentTime?: number;
  duration?: number;
}): boolean {
  if (status.didJustFinish) return true;
  const duration = status.duration ?? 0;
  const current = status.currentTime ?? 0;
  return duration > 0 && current >= duration - 0.04;
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
