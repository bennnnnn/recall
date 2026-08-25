import {
  chatSuggestionLoadAction,
  chatTurnHomeRefreshOpts,
  shouldFetchChatSuggestions,
} from "@/lib/chatTurnRefresh";

describe("chatSuggestionLoadAction", () => {
  it("clears when signed out or the thread is empty", () => {
    expect(
      chatSuggestionLoadAction({
        hasToken: false,
        hasMessages: true,
        turnBusy: false,
      }),
    ).toBe("clear");
    expect(
      chatSuggestionLoadAction({
        hasToken: true,
        hasMessages: false,
        turnBusy: false,
      }),
    ).toBe("clear");
  });

  it("holds while a send is in flight or the reply is streaming", () => {
    expect(
      chatSuggestionLoadAction({
        hasToken: true,
        hasMessages: true,
        turnBusy: true,
      }),
    ).toBe("hold");
  });

  it("loads after the turn, or when opening a finished thread", () => {
    expect(
      chatSuggestionLoadAction({
        hasToken: true,
        hasMessages: true,
        turnBusy: false,
      }),
    ).toBe("load");
  });
});

describe("shouldFetchChatSuggestions", () => {
  it("does not fetch on stream-end until refreshKey bumps", () => {
    expect(
      shouldFetchChatSuggestions({
        action: "load",
        refreshKeyChanged: false,
        openedIdleThread: false,
      }),
    ).toBe(false);
  });

  it("fetches once after the turn, or once when opening a finished thread", () => {
    expect(
      shouldFetchChatSuggestions({
        action: "load",
        refreshKeyChanged: true,
        openedIdleThread: false,
      }),
    ).toBe(true);
    expect(
      shouldFetchChatSuggestions({
        action: "load",
        refreshKeyChanged: false,
        openedIdleThread: true,
      }),
    ).toBe(true);
  });

  it("does not fetch while holding or clearing", () => {
    expect(
      shouldFetchChatSuggestions({
        action: "hold",
        refreshKeyChanged: true,
        openedIdleThread: true,
      }),
    ).toBe(false);
    expect(
      shouldFetchChatSuggestions({
        action: "clear",
        refreshKeyChanged: true,
        openedIdleThread: true,
      }),
    ).toBe(false);
  });
});

describe("chatTurnHomeRefreshOpts", () => {
  it("does not bypass the 20s Home cache after a chat turn", () => {
    expect(chatTurnHomeRefreshOpts()).toEqual({ silent: true });
    expect(chatTurnHomeRefreshOpts()).not.toHaveProperty("force");
  });
});
