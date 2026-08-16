import {
  alignPcmBytes,
  concatBytes,
  looksLikeMpeg,
  pcmToWavBytes,
  TTS_FIRST_CLIP_BYTES,
} from "@/lib/ttsPcm";

describe("ttsPcm", () => {
  it("detects ID3 and MPEG sync frames", () => {
    expect(looksLikeMpeg(new Uint8Array([0x49, 0x44, 0x33, 0x04]))).toBe(true);
    expect(looksLikeMpeg(new Uint8Array([0xff, 0xfb, 0x90, 0x00]))).toBe(true);
    expect(looksLikeMpeg(new Uint8Array([0x00, 0x00, 0x01, 0x00]))).toBe(false);
  });

  it("aligns PCM to 16-bit frames", () => {
    expect(alignPcmBytes(7)).toBe(6);
    expect(alignPcmBytes(8)).toBe(8);
  });

  it("concatenates byte arrays", () => {
    const out = concatBytes(new Uint8Array([1, 2]), new Uint8Array([3]));
    expect(Array.from(out)).toEqual([1, 2, 3]);
  });

  it("wraps PCM in a WAV header", () => {
    const pcm = new Uint8Array(TTS_FIRST_CLIP_BYTES);
    const wav = pcmToWavBytes(pcm, 24000);
    expect(String.fromCharCode(...wav.subarray(0, 4))).toBe("RIFF");
    expect(String.fromCharCode(...wav.subarray(8, 12))).toBe("WAVE");
    expect(wav.length).toBe(44 + pcm.length);
  });
});
