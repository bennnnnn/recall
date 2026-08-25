import {
  chatSuggestionLoadAction,
  chatTurnHomeRefreshOpts,
} from "@/lib/chatTurnRefresh";

describe("chatSuggestionLoadAction", () => {
  it("clears when signed out or the thread is empty", () => {
    expect(
      chatSuggestionLoadAction({
        hasToken: false,
        hasMessages: true,
        streamActive: false,
      }),
    ).toBe("clear");
    expect(
      chatSuggestionLoadAction({
        hasToken: true,
        hasMessages: false,
        streamActive: false,
      }),
    ).toBe("clear");
  });

  it("holds while the first user bubble is on screen and the reply is still streaming", () => {
    expect(
      chatSuggestionLoadAction({
        hasToken: true,
        hasMessages: true,
        streamActive: true,
      }),
    ).toBe("hold");
  });

  it("loads after the turn, or when opening a finished thread", () => {
    expect(
      chatSuggestionLoadAction({
        hasToken: true,
        hasMessages: true,
        streamActive: false,
      }),
    ).toBe("load");
  });
});

describe("chatTurnHomeRefreshOpts", () => {
  it("does not bypass the 20s Home cache after a chat turn", () => {
    expect(chatTurnHomeRefreshOpts()).toEqual({ silent: true });
    expect(chatTurnHomeRefreshOpts()).not.toHaveProperty("force");
  });
});
