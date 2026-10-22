import { useEffect } from "react";
import { Keyboard, Platform } from "react-native";

import { useComposerDraftActivity } from "@/contexts/ComposerDraftContext";
import { shouldWarmDraftSocket } from "@/features/chat/model/draftLogic";

type Options = {
  token: string | null;
  chatId: string | null;
  streaming: boolean;
  draftChatId: string | null;
  connect: () => void | Promise<void>;
};

/**
 * Opens the chat socket before a send needs it: a draft chat's as soon as the
 * draft exists, and again whenever the user starts to write (the keyboard comes
 * up, or the composer gets its first character). The server closes a socket left
 * idle for five minutes; reopening on intent, not on a timer, keeps that close
 * while the send still finds the socket open. `connect` does nothing when it is.
 */
export function useChatDraftWarmup({
  token,
  chatId,
  streaming,
  draftChatId,
  connect,
}: Options) {
  const composing = useComposerDraftActivity();

  useEffect(() => {
    if (!shouldWarmDraftSocket({ token, draftChatId, chatId, streaming })) return;
    void connect();
  }, [token, draftChatId, chatId, streaming, connect]);

  useEffect(() => {
    if (composing) void connect();
  }, [composing, connect]);

  useEffect(() => {
    const event = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const sub = Keyboard.addListener(event, () => void connect());
    return () => sub.remove();
  }, [connect]);
}
