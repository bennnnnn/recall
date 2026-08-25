import {
  CONTEXT_REFRESH_STALE_MS,
  isContextFresh,
  shouldRefreshHomeOnChatFocus,
} from "@/lib/cache/contextRefresh";

describe("isContextFresh", () => {
  it("treats missing timestamps as stale", () => {
    expect(isContextFresh(undefined)).toBe(false);
  });

  it("is fresh inside the stale window and stale after", () => {
    const now = 1_000_000;
    expect(isContextFresh(now - CONTEXT_REFRESH_STALE_MS + 1, now)).toBe(true);
    expect(isContextFresh(now - CONTEXT_REFRESH_STALE_MS, now)).toBe(false);
  });
});

describe("shouldRefreshHomeOnChatFocus", () => {
  it("skips /home when a thread is already open", () => {
    expect(shouldRefreshHomeOnChatFocus(true)).toBe(false);
    expect(shouldRefreshHomeOnChatFocus(false)).toBe(true);
  });
});
