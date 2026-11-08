import { abortError } from "@/lib/api/deadline";
import {
  ensureChunk,
  ensurePrefetchState,
  prefetchChunk,
  type ClipVoice,
} from "@/features/speech/model/ttsClipFetch";

jest.mock("@/lib/api/client", () => ({ requestRaw: jest.fn() }));
jest.mock("@/lib/markdown/plain", () => ({ markdownToSpeechText: (text: string) => text }));
jest.mock("@/features/speech/model/ttsLead", () => ({
  splitTtsChunks: (text: string) => text.split("|"),
}));

const { requestRaw } = jest.requireMock<{ requestRaw: jest.Mock }>("@/lib/api/client");

/** A clip request that waits until its signal aborts, then rejects as the API client does. */
function downloadUntilCancelled(): void {
  requestRaw.mockImplementationOnce(
    (_path: string, _token: string, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener("abort", () => reject(abortError()));
      }),
  );
}

let readings = 0;
/** A reply of two clips, read for the first time. */
function freshReading() {
  readings += 1;
  return ensurePrefetchState(`first ${readings}|second ${readings}`, VOICE);
}

const VOICE: ClipVoice = { model: "speech-tts-model", voice: null, language: "en-US" };
const clip = (audio: string) => ({ ok: true, json: async () => ({ audio_base64: audio, content_type: "audio/mpeg" }) });

describe("a clip fetched ahead of the reading", () => {
  beforeEach(() => {
    requestRaw.mockReset();
    jest.spyOn(console, "info").mockImplementation(() => {});
  });
  afterEach(() => jest.restoreAllMocks());

  it("settles, unreported, when Stop cancels its download", async () => {
    const state = freshReading();
    const stop = new AbortController();
    downloadUntilCancelled();

    const prefetch = prefetchChunk(state, 1, "tok", stop.signal);
    stop.abort();

    // Left unhandled, this rejection reached the console as "Uncaught (in promise)".
    await expect(prefetch).resolves.toBeUndefined();
    expect(console.info).not.toHaveBeenCalled();
    expect(state.inflight[1]).toBeNull();
  });

  it("settles when its download fails, and the reading asks for the clip again", async () => {
    const state = freshReading();
    requestRaw.mockRejectedValueOnce(new TypeError("Network request failed"));

    await expect(prefetchChunk(state, 1, "tok", new AbortController().signal)).resolves.toBeUndefined();
    expect(console.info).toHaveBeenCalledWith(
      "[tts-latency]",
      expect.objectContaining({ stage: "prefetch_failed", chunk: 1, error: "TypeError" }),
    );

    requestRaw.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ audio_base64: "QUJD", content_type: "audio/mpeg" }),
    });
    await expect(ensureChunk(state, 1, "tok", new AbortController().signal)).resolves.toMatchObject({
      audio_base64: "QUJD",
    });
    expect(requestRaw).toHaveBeenCalledTimes(2);
  });

  it("is the clip the reading then awaits, and a cancel resolves it to nothing", async () => {
    const state = freshReading();
    const stop = new AbortController();
    downloadUntilCancelled();

    const prefetch = prefetchChunk(state, 1, "tok", stop.signal);
    const awaited = ensureChunk(state, 1, "tok", stop.signal);
    stop.abort();

    await expect(awaited).resolves.toBeNull();
    await expect(prefetch).resolves.toBeUndefined();
    expect(requestRaw).toHaveBeenCalledTimes(1);
  });

  it("takes the request's own deadline for a failure, not a Stop", async () => {
    // A deadline is an AbortError too, with the reading's own signal untouched.
    const reading = new AbortController();
    requestRaw.mockRejectedValueOnce(abortError());
    await expect(ensureChunk(freshReading(), 1, "tok", reading.signal)).rejects.toMatchObject({
      name: "AbortError",
    });

    requestRaw.mockRejectedValueOnce(abortError());
    await expect(prefetchChunk(freshReading(), 1, "tok", reading.signal)).resolves.toBeUndefined();
    expect(console.info).toHaveBeenCalledWith(
      "[tts-latency]",
      expect.objectContaining({ stage: "prefetch_failed", chunk: 1, error: "AbortError" }),
    );
  });
});

// Change the voice, replay the same reply: the clip kept for the old voice played.
describe("the clips kept for a reply", () => {
  beforeEach(() => requestRaw.mockReset());

  it("are the reply's while its voice, model and language stay the same", async () => {
    const text = "kept|reply";
    requestRaw.mockResolvedValueOnce(clip("QUJD"));
    const first = ensurePrefetchState(text, VOICE);
    await ensureChunk(first, 0, "tok", new AbortController().signal);
    expect(ensurePrefetchState(text, { ...VOICE })).toBe(first);
    expect(requestRaw).toHaveBeenCalledTimes(1);
  });

  it.each<[string, Partial<ClipVoice>]>([
    ["voice", { voice: "cedar" }],
    ["model", { model: "speech-tts-fast-model" }],
    ["language", { language: "de-DE" }],
  ])("are asked for again when the %s changes, in that language", async (what, change) => {
    const text = `changed ${what}|reply`;
    requestRaw.mockResolvedValueOnce(clip("T0xE")).mockResolvedValueOnce(clip("TkVX"));
    const before = ensurePrefetchState(text, VOICE);
    await ensureChunk(before, 0, "tok", new AbortController().signal);
    const after = ensurePrefetchState(text, { ...VOICE, ...change });
    expect(after).not.toBe(before);
    await expect(ensureChunk(after, 0, "tok", new AbortController().signal)).resolves.toMatchObject({ audio_base64: "TkVX" });
    const body = JSON.parse(requestRaw.mock.calls[1]?.[2]?.body as string) as Record<string, string>;
    expect(body).toMatchObject({ language: change.language ?? "en-US", model: change.model ?? "speech-tts-model" });
  });
});
