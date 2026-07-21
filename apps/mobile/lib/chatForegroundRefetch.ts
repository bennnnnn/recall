import type { AppStateStatus } from "react-native";

/** Gate for silently reloading chat messages when the app returns to foreground. */
export function shouldRefetchChatOnForeground(opts: {
  appState: AppStateStatus;
  token: string | null;
  chatId: string | null;
  streaming: boolean;
  chatLoading: boolean;
}): boolean {
  return (
    opts.appState === "active" &&
    Boolean(opts.token) &&
    Boolean(opts.chatId) &&
    !opts.streaming &&
    !opts.chatLoading
  );
}
