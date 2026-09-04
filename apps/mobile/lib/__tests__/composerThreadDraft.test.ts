import {
  COMPOSER_NEW_THREAD_KEY,
  adoptNewComposerThread,
  composerThreadKey,
  takeThreadDraft,
} from "@/lib/chat/composerThreadDraft";

describe("composerThreadKey", () => {
  it("uses the route chat id when present", () => {
    expect(composerThreadKey("chat-1")).toBe("chat-1");
  });

  it("uses the New Chat slot when the route has no chat", () => {
    expect(composerThreadKey(undefined)).toBe(COMPOSER_NEW_THREAD_KEY);
    expect(composerThreadKey(null)).toBe(COMPOSER_NEW_THREAD_KEY);
    expect(composerThreadKey("")).toBe(COMPOSER_NEW_THREAD_KEY);
  });
});

describe("takeThreadDraft", () => {
  it("is a no-op when the thread did not change", () => {
    const drafts = new Map<string, string>();
    expect(takeThreadDraft(drafts, "a", "a", "hello")).toBe("hello");
    expect(drafts.size).toBe(0);
  });

  it("saves the leaving draft and restores the next thread", () => {
    const drafts = new Map<string, string>([["b", "from b"]]);
    expect(takeThreadDraft(drafts, "a", "b", "from a")).toBe("from b");
    expect(drafts.get("a")).toBe("from a");
  });

  it("restores empty when the next thread has no saved draft", () => {
    const drafts = new Map<string, string>();
    expect(takeThreadDraft(drafts, "a", "b", "from a")).toBe("");
    expect(drafts.get("a")).toBe("from a");
  });
});

describe("adoptNewComposerThread", () => {
  it("moves New Chat onto the created id without swapping the visible text", () => {
    const drafts = new Map<string, string>();
    expect(
      adoptNewComposerThread(drafts, COMPOSER_NEW_THREAD_KEY, "created", "follow-up"),
    ).toBe("created");
    expect(drafts.get(COMPOSER_NEW_THREAD_KEY)).toBe("");
    expect(drafts.get("created")).toBe("follow-up");
  });

  it("does not steal another thread if the user left New Chat during create", () => {
    const drafts = new Map<string, string>([["other", "keep me"]]);
    expect(
      adoptNewComposerThread(drafts, "other", "created", "typed on other"),
    ).toBe("other");
    expect(drafts.get("created")).toBeUndefined();
    expect(drafts.get("other")).toBe("keep me");
  });
});
