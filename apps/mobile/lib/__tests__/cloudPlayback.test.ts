import { arrayBufferToBase64 } from "@/lib/base64";
import {
  playbackStatusFinished,
  playbackWaitMs,
  wavDurationMsFromBase64,
} from "@/lib/cloudPlayback";

function pcmToWavBase64(pcm: Uint8Array, sampleRate = 24000): string {
  const header = new ArrayBuffer(44);
  const view = new DataView(header);
  const dataSize = pcm.byteLength;
  view.setUint32(0, 0x52494646, false); // RIFF
  view.setUint32(4, 36 + dataSize, true);
  view.setUint32(8, 0x57415645, false); // WAVE
  view.setUint32(12, 0x666d7420, false); // fmt
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  view.setUint32(36, 0x64617461, false); // data
  view.setUint32(40, dataSize, true);
  const wav = new Uint8Array(44 + dataSize);
  wav.set(new Uint8Array(header), 0);
  wav.set(pcm, 44);
  return arrayBufferToBase64(wav.buffer);
}

describe("cloudPlayback", () => {
  it("reads duration from a PCM WAV header", () => {
    const pcm = new Uint8Array(24000 * 2); // 1s
    const b64 = pcmToWavBase64(pcm);
    expect(wavDurationMsFromBase64(b64)).toBe(1000);
  });

  it("caps wait to duration plus slack", () => {
    expect(playbackWaitMs(350)).toBe(750);
    expect(playbackWaitMs(null)).toBe(20_000);
  });

  it("finishes on didJustFinish or currentTime at duration", () => {
    expect(playbackStatusFinished({ didJustFinish: true })).toBe(true);
    expect(playbackStatusFinished({ currentTime: 0.74, duration: 0.75 })).toBe(true);
    expect(playbackStatusFinished({ currentTime: 0.1, duration: 0.75 })).toBe(false);
  });
});
