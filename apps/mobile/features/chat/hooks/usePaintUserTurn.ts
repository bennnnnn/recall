import { useCallback, type MutableRefObject } from "react";
import { Keyboard } from "react-native";

import type { PendingAttachment } from "@/features/attachments/model/attachments";
import type { SendTurnStart } from "@/features/chat/hooks/useTurnStart";
import { markChatBubblePainted, markChatTtftStart } from "@/features/chat/model/latency";
import { buildOptimisticUserMessage } from "@/features/chat/model/sendLogic";
import type { EditThread } from "@/features/chat/model/threadEdit";

/** What painting a send does to the composer: empty it, leave it (a tapped line), or nothing (emptied at the tap). */
type ComposerOnPaint = "clear" | "leave" | "cleared";

type Options = {
  setInput: (text: string) => void;
  setPendingAttachment: (attachment: PendingAttachment | null) => void;
  setPendingOutboundId: (id: string | null) => void;
  editThread: EditThread;
  newMessageCountRef: MutableRefObject<number>;
  sendStart: SendTurnStart;
};

/** The composer emptied by a send, and the user's bubble that send paints. */
export function usePaintUserTurn({
  setInput, setPendingAttachment, setPendingOutboundId, editThread, newMessageCountRef, sendStart,
}: Options) {
  /** Empties the composer and puts the keyboard down, as a tap on Send does. */
  const clearComposer = useCallback(() => {
    setInput("");
    setPendingAttachment(null);
    Keyboard.dismiss();
  }, [setInput, setPendingAttachment]);

  /** Clears the composer (as `composer` says) and paints the user's bubble, with typing dots when they can go up. */
  const paintUserTurn = useCallback((text: string, attached: PendingAttachment | null, tappedAt: number, composer: ComposerOnPaint) => {
    // Clear the composer immediately so the next draft can be typed.
    // Keep Send/Attach busy until the turn is accepted — an idle button
    // with sendInFlightRef set looked finished and ate the next tap.
    if (composer === "clear") clearComposer();
    // A tapped line leaves the draft, but its keyboard goes down as a send's does. One cleared
    // at the tap put it down then: a keyboard up now is the next draft being typed.
    else if (composer === "leave") Keyboard.dismiss();

    const optimisticId = `local-${tappedAt}`;
    const createdAt = new Date(tappedAt).toISOString();
    // From the tap, not the paint: anything that ever delays the bubble counts.
    markChatTtftStart(optimisticId, tappedAt, Boolean(attached));
    setPendingOutboundId(optimisticId);
    editThread(
      (prev) => [...prev, buildOptimisticUserMessage({ text, attached, optimisticId, createdAt })],
      "optimistic_send",
    );
    newMessageCountRef.current += 1;
    requestAnimationFrame(() => markChatBubblePainted(optimisticId));
    return { optimisticId, dots: sendStart.beginDots() };
  }, [clearComposer, setPendingOutboundId, editThread, newMessageCountRef, sendStart]);

  return { clearComposer, paintUserTurn };
}
