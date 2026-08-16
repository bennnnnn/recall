/** 16-bit little-endian PCM helpers for streamed cloud TTS. */

export const TTS_PCM_SAMPLE_RATE = 24000;
export const TTS_PCM_CHANNELS = 1;

/** ~120ms at 24 kHz mono 16-bit — start playback before the rest arrives. */
export const TTS_FIRST_CLIP_BYTES = 5760;
/** Later clips ~280ms so the player is not hopping every frame. */
export const TTS_NEXT_CLIP_BYTES = 13440;

export function looksLikeMpeg(bytes: Uint8Array): boolean {
  if (bytes.length >= 3 && bytes[0] === 0x49 && bytes[1] === 0x44 && bytes[2] === 0x33) {
    return true;
  }
  return bytes.length >= 2 && bytes[0] === 0xff && (bytes[1] & 0xe0) === 0xe0;
}

export function alignPcmBytes(length: number): number {
  return length - (length % 2);
}

export function concatBytes(left: Uint8Array, right: Uint8Array): Uint8Array {
  const out = new Uint8Array(left.length + right.length);
  out.set(left, 0);
  out.set(right, left.length);
  return out;
}

export function uint8ToBase64(bytes: Uint8Array): string {
  const chunk = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export function pcmToWavBytes(
  pcm: Uint8Array,
  sampleRate = TTS_PCM_SAMPLE_RATE,
): Uint8Array {
  const dataSize = pcm.length;
  const header = new ArrayBuffer(44);
  const view = new DataView(header);
  const writeAscii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  };
  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, TTS_PCM_CHANNELS, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * TTS_PCM_CHANNELS * 2, true);
  view.setUint16(32, TTS_PCM_CHANNELS * 2, true);
  view.setUint16(34, 16, true);
  writeAscii(36, "data");
  view.setUint32(40, dataSize, true);
  const out = new Uint8Array(44 + dataSize);
  out.set(new Uint8Array(header), 0);
  out.set(pcm, 44);
  return out;
}
