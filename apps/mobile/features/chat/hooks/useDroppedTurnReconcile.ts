import { useCallback, type MutableRefObject } from "react";

import { api, type Message } from "@/lib/api";
import { MESSAGE_PAGE_SIZE } from "@/features/chat/model/constants";
import {
  knownServerIds,
  pollDroppedTurn,
  type DroppedTurnResult,
} from "@/features/chat/model/turnReconcile";

type Options = {
  token: string | null;
  chatId: string | null;
  isCurrentView: () => boolean;
  messagesRef: MutableRefObject<Message[]>;
  sendAttemptRef: MutableRefObject<number>;
  streamingRef: MutableRefObject<boolean>;
};

/**
 * Follows a turn the server took after its connection dropped: reload the chat
 * until the reply lands. The streaming bubble stays up meanwhile; Stop, a new
 * send or leaving the chat ends the wait without a settle.
 */
export function useDroppedTurnReconcile({
  token,
  chatId,
  isCurrentView,
  messagesRef,
  sendAttemptRef,
  streamingRef,
}: Options) {
  return useCallback(
    (settle: (result: DroppedTurnResult) => void, polls?: number, pollMs?: (poll: number) => number) => {
      if (!token || !chatId) {
        settle({ state: "unknown", page: null });
        return;
      }
      const attempt = sendAttemptRef.current;
      void pollDroppedTurn({
        fetchPage: async () =>
          (await api.listMessages(token, chatId, { limit: MESSAGE_PAGE_SIZE })).messages,
        known: knownServerIds(messagesRef.current),
        stillWaiting: () =>
          isCurrentView() && sendAttemptRef.current === attempt && streamingRef.current,
        polls,
        pollMs,
      }).then((result) => {
        if (result) settle(result);
      });
    },
    [token, chatId, isCurrentView, messagesRef, sendAttemptRef, streamingRef],
  );
}
