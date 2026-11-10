import { useEffect, useRef } from "react";

type Options = {
  /** The chat the composer writes into: the open one, or the new chat a first character made. */
  chatId: string | null;
  /** The composer holds a draft (`useComposerDraftActivity`). */
  composing: boolean;
  connect: () => void | Promise<void>;
};

/**
 * Opens the chat's socket at a draft's first character, so its send finds the handshake done:
 * on a slow cellular path the send otherwise waited for it, or fell back to SSE. Typed, not
 * shown: a chat opened or read opens none, nor one opened with a draft already saved in it.
 * The socket keeps its idle minute, so a draft left unsent costs one handshake. `connect`
 * does nothing when a socket is open.
 */
export function useChatDraftWarmup({ chatId, composing, connect }: Options) {
  const previous = useRef({ chatId, composing });
  useEffect(() => {
    const before = previous.current;
    previous.current = { chatId, composing };
    if (!composing || !chatId) return;
    // A first character in this chat, or the new chat a first character made.
    const typed = before.chatId === chatId ? !before.composing : before.chatId === null && before.composing;
    if (typed) void connect();
  }, [chatId, composing, connect]);
}
