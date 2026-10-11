export type ChatSuggestionLoad = "clear" | "hold" | "load";

/** Chips refetch after the turn — not when the user bubble first appears. */
export function chatSuggestionLoadAction(opts: {
  hasToken: boolean;
  hasMessages: boolean;
  turnBusy: boolean;
}): ChatSuggestionLoad {
  if (!opts.hasToken || !opts.hasMessages) return "clear";
  if (opts.turnBusy) return "hold";
  return "load";
}

/**
 * `load` is not enough: stream-end flips busy off before `refreshKey` bumps,
 * and an optimistic user bubble sits on screen before the socket is open.
 */
export function shouldFetchChatSuggestions(opts: {
  action: ChatSuggestionLoad;
  refreshKeyChanged: boolean;
  openedIdleThread: boolean;
}): boolean {
  if (opts.action !== "load") return false;
  return opts.refreshKeyChanged || opts.openedIdleThread;
}
