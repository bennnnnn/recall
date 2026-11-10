import { useEffect, useRef } from "react";

import type { Message } from "@/lib/api";
import { pendingPhotoDeadline } from "@/features/chat/model/latePhoto";
import { useLatestRef } from "@/lib/latestRef";

type Options = {
  /** The chat on screen; none for a new chat. */
  chatId: string | null;
  messages: Message[];
  /** The page is loading or a turn is under way: that read, or the turn, comes first. */
  busy: boolean;
  /** `silentRefetchChat`. */
  refetch: (chatId: string, cancelled: () => boolean, opts?: { force?: boolean }) => Promise<void>;
};

/**
 * A reply whose photo was still on its way gets it on its socket (`answer_photo`), which
 * clears the wait. When that socket went first (the app in the background, a network change,
 * another chat opened and this one again), nothing would bring the photo: the open chat reads
 * itself once at the wait's end, and the saved reply then holds the photo if one came
 * (review 2026-11-09: the phone locked 2 s after a reply, back at 8 s, the photo landed at 12 s
 * and never showed).
 */
export function useChatPendingPhotoRead({ chatId, messages, busy, refetch }: Options): void {
  const until = pendingPhotoDeadline(messages);
  const refetchRef = useLatestRef(refetch);
  /** The wait this view already read for: once, not again when the read changed nothing. */
  const readFor = useRef<string | null>(null);

  useEffect(() => {
    if (!chatId || until === null || busy) return;
    const wait = `${chatId}:${until}`;
    if (readFor.current === wait) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      readFor.current = wait;
      void refetchRef.current(chatId, () => cancelled, { force: true });
    }, Math.max(0, until - Date.now()));
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [chatId, until, busy, refetchRef]);
}
