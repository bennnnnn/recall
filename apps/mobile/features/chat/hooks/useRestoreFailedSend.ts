import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from "react";

import { useComposerDraftApi } from "@/contexts/ComposerDraftContext";
import { discardDraftAttachment, type PendingAttachment } from "@/features/attachments/model/attachments";
import { shouldRestoreFailedSend } from "@/features/chat/model/composerThreadDraft";
import { clearPendingChatTtft } from "@/features/chat/model/latency";
import type { Message } from "@/lib/api";

/** One send, from the tap that started it. */
export type SendTurn = {
  text: string;
  composerText: string;
  attachment: PendingAttachment | null;
  threadKey: string;
  isCurrentSession: () => boolean;
  isCurrentView: () => boolean;
};

type Options = {
  token: string | null;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  newMessageCountRef: MutableRefObject<number>;
  pendingAttachmentRef: MutableRefObject<PendingAttachment | null>;
  setPendingAttachment: (value: PendingAttachment | null) => void;
  stashAttachmentForThread: (key: string, openKey: string, attachment: PendingAttachment | null) => void;
  setPendingOutboundId: (id: string | null) => void;
  sendInFlightRef: MutableRefObject<boolean>;
  setSendPhase: (phase: "idle") => void;
};

/** Takes the bubble back and returns the draft (text and file) to the thread it was typed in. */
export function useRestoreFailedSend({
  token,
  setMessages,
  newMessageCountRef,
  pendingAttachmentRef,
  setPendingAttachment,
  stashAttachmentForThread,
  setPendingOutboundId,
  sendInFlightRef,
  setSendPhase,
}: Options) {
  const { setInput, inputRef, stashFailedDraftForThread, getThreadKey } = useComposerDraftApi();
  return useCallback(
    (turn: SendTurn, optimisticId: string, attached: PendingAttachment | null) => {
      clearPendingChatTtft(optimisticId);
      if (!turn.isCurrentSession()) {
        discardDraftAttachment(null, attached);
        return;
      }
      // The attachment travels with the text: uploaded, it keeps its id for the next send.
      const stash = () => {
        stashFailedDraftForThread(turn.threadKey, turn.text);
        stashAttachmentForThread(turn.threadKey, getThreadKey(), attached);
      };
      if (!turn.isCurrentView()) {
        stash();
        return;
      }
      setPendingOutboundId(null);
      setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
      newMessageCountRef.current = Math.max(0, newMessageCountRef.current - 1);
      if (getThreadKey() === turn.threadKey) {
        if (!pendingAttachmentRef.current && shouldRestoreFailedSend(inputRef.current, turn.text)) {
          setInput(turn.text);
          setPendingAttachment(attached);
        } else {
          discardDraftAttachment(token, attached);
        }
      } else {
        stash();
      }
      sendInFlightRef.current = false;
      setSendPhase("idle");
    },
    [
      stashFailedDraftForThread, stashAttachmentForThread, setMessages, newMessageCountRef, getThreadKey,
      pendingAttachmentRef, inputRef, setInput, setPendingAttachment, token, setPendingOutboundId,
      sendInFlightRef, setSendPhase,
    ],
  );
}
