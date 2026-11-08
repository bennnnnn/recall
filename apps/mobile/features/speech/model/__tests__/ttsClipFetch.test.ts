import { abortError } from "@/lib/api/deadline";
import { ensureChunk, ensurePrefetchState, prefetchChunk } from "@/features/speech/model/ttsClipFetch";

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
  return ensurePrefetchState(`first ${readings}|second ${readings}`, "speech-tts-model");
}

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

    const prefetch = prefetchChunk(state, 1, "tok", "en-US", stop.signal);
    stop.abort();

    // Left unhandled, this rejection reached the console as "Uncaught (in promise)".
    await expect(prefetch).resolves.toBeUndefined();
    expect(console.info).not.toHaveBeenCalled();
    expect(state.inflight[1]).toBeNull();
  });

  it("settles when its download fails, and the reading asks for the clip again", async () => {
    const state = freshReading();
    requestRaw.mockRejectedValueOnce(new TypeError("Network request failed"));

    await expect(prefetchChunk(state, 1, "tok", "en-US", new AbortController().signal)).resolves.toBeUndefined();
    expect(console.info).toHaveBeenCalledWith(
      "[tts-latency]",
      expect.objectContaining({ stage: "prefetch_failed", chunk: 1, error: "TypeError" }),
    );

    requestRaw.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ audio_base64: "QUJD", content_type: "audio/mpeg" }),
    });
    await expect(ensureChunk(state, 1, "tok", "en-US", new AbortController().signal)).resolves.toMatchObject({
      audio_base64: "QUJD",
    });
    expect(requestRaw).toHaveBeenCalledTimes(2);
  });

  it("is the clip the reading then awaits, and a cancel resolves it to nothing", async () => {
    const state = freshReading();
    const stop = new AbortController();
    downloadUntilCancelled();

    const prefetch = prefetchChunk(state, 1, "tok", "en-US", stop.signal);
    const awaited = ensureChunk(state, 1, "tok", "en-US", stop.signal);
    stop.abort();

    await expect(awaited).resolves.toBeNull();
    await expect(prefetch).resolves.toBeUndefined();
    expect(requestRaw).toHaveBeenCalledTimes(1);
  });
});
