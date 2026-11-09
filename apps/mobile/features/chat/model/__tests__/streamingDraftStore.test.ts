import {
  getStreamingDraft,
  publishStreamingDraft,
  resetStreamingDraftStoreForTest,
  subscribeStreamingDraft,
} from "@/features/chat/model/streamingDraftStore";

describe("streamingDraftStore", () => {
  afterEach(() => {
    resetStreamingDraftStoreForTest();
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
    expect(getStreamingDraft()?.content).toHaveLength(11);
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
    expect(getStreamingDraft()).toBeNull();
  });
});
