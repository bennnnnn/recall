/** After a chat turn, refresh Home only if the 20s cache is stale. */
export function chatTurnHomeRefreshOpts(): { silent: true } {
  return { silent: true };
}

export type ChatSuggestionLoad = "clear" | "hold" | "load";

/** Chips refetch after the turn — not when the user bubble first appears. */
export function chatSuggestionLoadAction(opts: {
  hasToken: boolean;
  hasMessages: boolean;
  streamActive: boolean;
}): ChatSuggestionLoad {
  if (!opts.hasToken || !opts.hasMessages) return "clear";
  if (opts.streamActive) return "hold";
  return "load";
}
