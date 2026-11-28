import { useEffect, type RefObject } from "react";

import { useComposerDraftApiOptional } from "@/features/chat/context/ComposerDraftContext";
import type { ChatTurnEvent, ChatTurnState } from "@/features/chat/model/chatTurnCore";
import { giveBackToNewChat } from "@/features/chat/model/openedPage";
import { onAppEvent } from "@/lib/appEvents";
import { useLatestRef } from "@/lib/latestRef";

/**
 * A send the server refused waits under Retry on its chat. Once that chat is deleted (on
 * another device, found by the refusal itself, or here), nothing reaches it any more: its
 * unsent turns go back to New chat's composer, text and file, and leave the chat (review of
 * #2621: a message typed into a chat deleted on the laptop was lost).
 */
export function useUnsentOfDeletedChats(turn: RefObject<ChatTurnState>, step: (event: ChatTurnEvent) => void): void {
  const composer = useLatestRef(useComposerDraftApiOptional());
  useEffect(() => onAppEvent("chatsDeleted", ({ chatIds }) => {
    for (const chatId of chatIds) {
      const unsent = turn.current.rejected.get(chatId);
      if (!unsent?.length) continue;
      step({ type: "rejected_dropped", chatId });
      giveBackToNewChat([...unsent], composer.current);
    }
  }), [turn, step, composer]);
}
