import {
  getStreamingDraft,
  getStreamingDraftContentLength,
  publishStreamingDraft,
  resetStreamingDraftStore,
  subscribeStreamingDraft,
} from "@/lib/streamingDraftStore";

describe("streamingDraftStore", () => {
  afterEach(() => {
    resetStreamingDraftStore();
  });

  it("publishes draft updates to subscribers", () => {
    const seen: string[] = [];
    const unsubscribe = subscribeStreamingDraft(() => {
      seen.push(getStreamingDraft()?.content ?? "");
    });

    publishStreamingDraft({ content: "hello" });
    publishStreamingDraft({ content: "hello world" });
    unsubscribe();

    expect(seen).toEqual(["hello", "hello world"]);
    expect(getStreamingDraftContentLength()).toBe(11);
  });

  it("clears draft and notifies subscribers", () => {
    let latest: string | null = "pending";
    const unsubscribe = subscribeStreamingDraft(() => {
      latest = getStreamingDraft()?.content ?? null;
    });

    publishStreamingDraft({ content: "partial" });
    publishStreamingDraft(null);
    unsubscribe();

    expect(latest).toBeNull();
    expect(getStreamingDraftContentLength()).toBe(0);
  });
});
